from __future__ import print_function
from lxml import etree
from lxml.builder import ElementMaker
import time
import calendar
from re import sub
import logging
import os


def add_ns(_tag, namespace):
    """
    :param str namespace:
    :param str _tag:
    :return:
    :rtype: str
    """
    return sub(r"""/(?=\w+)""", '/{{{ns}}}', _tag).format(ns=namespace)


def merge(file1, file2):
    """Merging 2 tcx files

    :param file1:
    :param file2:
    :return:
    """
    logger = logging.getLogger(__name__)
    lh = logging.StreamHandler()
    lh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    lh.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(lh)

    assert os.path.isfile(file1)
    assert os.path.isfile(file2)

    tcx1_root = etree.parse(file1).getroot()
    tcx2_root = etree.parse(file2).getroot()
    default_ns = """http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"""

    e = ElementMaker(nsmap=tcx1_root.nsmap, namespace=default_ns)

    header_tags = {'TotalTimeSeconds', 'DistanceMeters', 'MaximumSpeed', 'Calories', 'AverageHeartRateBpm',
                   'MaximumHeartRateBpm', 'Intensity'}
    time_format = '%Y-%m-%dT%H:%M:%SZ'
    time_format2 = '%Y-%m-%dT%H:%M:%S.%fZ'

    def get_stats(tcx_root):
        """
        :param etree._Element tcx_root: root element of tcx file
        :rtype: dict[str, etree._Element]
        """
        return dict([(_tag, tcx_root.find(add_ns('.//Lap/{0}'.format(_tag), default_ns))) for _tag in header_tags])

    stats1 = get_stats(tcx1_root)
    stats2 = get_stats(tcx2_root)
    header = dict()

    def text(_el):
        if not _el:
            return ''
        if not _el.getchildren():
            return _el.text
        return _el.getchildren()[0].text

    for tag_key in header_tags:
        logger.debug('%s: %s', stats1[tag_key], text(stats1[tag_key]))
        logger.debug('%s: %s', stats2[tag_key], text(stats2[tag_key]))
        t_res = max(stats1[tag_key], stats2[tag_key], key=text)
        logger.debug('res: %s', text(t_res))
        header.update({tag_key: text(t_res)})

    logger.debug(r"""Merged header will contain: {0}""".format(header))

    def get_track_points(tcx_root):
        """
        :param etree._Element tcx_root:
        :return:
        :rtype: list[etree._Element]
        """
        track_points = tcx_root.findall(add_ns(""".//Lap/Track/Trackpoint""", default_ns))
        logger.debug('{0} track points found in track {1}'.format(len(track_points), tcx_root))
        return track_points

    def strp_dif_formats(_time):
        try:
            res = calendar.timegm(time.strptime(_time, time_format))
        except ValueError:
            res = calendar.timegm(time.strptime(_time, time_format2))
        return res

    def get_point_time(point):
        """
        :param etree._Element point:
        :rtype: int
        """
        _time = point.find(add_ns('./Time', default_ns)).text
        seconds = strp_dif_formats(_time)
        return seconds

    points = get_track_points(tcx1_root) + get_track_points(tcx2_root)
    points.sort(key=get_point_time)  # points sorted by time

    def get_lap_time(_lap):
        """
        :param etree._Element _lap:
        :rtype: int
        """
        _time = _lap.attrib['StartTime']
        logger.debug('Lap with start time %s', _time)
        return strp_dif_formats(_time)

    def format_time(seconds):
        """
        :param int seconds:
        :rtype: str
        """
        return time.strftime(time_format, time.gmtime(seconds))

    lap_path = add_ns('.//Lap', default_ns)
    lap_time = min(get_lap_time(tcx1_root.find(lap_path)), get_lap_time(tcx2_root.find(lap_path)))
    activity_id = format_time(get_point_time(points[0]) - 60)  # not duplicating activity in strava
    lap_start = format_time(lap_time)

    head = []
    for h in header:
        el = etree.Element(h)
        el.text = header[h]
        if el.tag not in ('MaximumHeartRateBpm', 'AverageHeartRateBpm'):
            head.append(el)

    head.extend(points)

    basic = e.TrainingCenterDatabase(
        e.Activities(
            e.Activity(
                e.Id(activity_id),
                e.Lap(
                    e.MaximumHeartRateBpm(
                        e.Value(header['MaximumHeartRateBpm']),
                        type='HeartRateInBeatsPerMinute_t'
                    ),
                    e.AverageHeartRateBpm(
                        e.Value(header['AverageHeartRateBpm']),
                        type='HeartRateInBeatsPerMinute_t'
                    ),
                    e.TriggerMethod('Manual'),
                    *head,
                    StartTime=lap_start
                ),
                Sport='Biking')
        )
    )

    basic = etree.tostring(basic, pretty_print=True, encoding="UTF-8", xml_declaration=True).replace('xsi:type', 'type')

    with open('output.xml', 'w+') as o:
        o.write(basic)


def parse_args():
    from argparse import ArgumentParser
    ap = ArgumentParser(description='merging 2 tcx files just sorting their tags')
    ap.add_argument('file1')
    ap.add_argument('file2')
    return ap.parse_args()


if __name__ == '__main__':
    ARGS = parse_args()
    merge(file1=ARGS.file1, file2=ARGS.file2)
