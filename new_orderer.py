from __future__ import print_function

import calendar
import logging
import time
from re import sub

from lxml import etree
from lxml.builder import ElementMaker

logger = logging.getLogger(__name__)
lh = logging.StreamHandler()
lh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
lh.setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)
logger.addHandler(lh)


def merge(file1="input/2016_06_25__16_51.tcx", file2="input/7169691758851211.tcx", out_file="output/result.tcx"):
    file1_root = etree.parse(file1).getroot()
    file2_root = etree.parse(file2).getroot()

    header_tags = {'TotalTimeSeconds', 'DistanceMeters', 'MaximumSpeed', 'Calories', 'AverageHeartRateBpm',
                   'MaximumHeartRateBpm', 'Intensity'}
    time_format = '%Y-%m-%dT%H:%M:%SZ'
    time_format2 = '%Y-%m-%dT%H:%M:%S.%fZ'

    default_ns = file1_root.nsmap[None]  # getting default namespace

    def add_ns(_tag, namespace):
        """
        :param str namespace:
        :param str _tag:
        :return:
        :rtype: str
        """
        return sub(r"""/(?=\w+)""", '/{{{ns}}}', _tag).format(ns=namespace)

    def track_points(root):
        """

        :param root:
        :return:
        :rtype: list[etree.ElementBase]
        """
        return root.findall(add_ns(".//Trackpoint", default_ns))

    def point_odometer(_point):
        odo = _point.find(add_ns("./DistanceMeters", default_ns))
        if odo is not None:
            odo = float(odo.text)
        return odo

    def point_time(_point):
        """

        :param _point:
        :return:
        :rtype: etree.ElementBase
        """
        return _point.find(add_ns("./Time", default_ns))

    def point_position(_point):
        return _point.find(add_ns("./Position", default_ns))

    track_points_all = track_points(file1_root)
    track_points_all.extend(track_points(file2_root))

    track_points_all.sort(key=point_odometer)

    for i in range(len(track_points_all)):
        point = track_points_all[i]
        if point_position(point) is None:
            logger.info(point_position(point))
            try:
                next_time = point_time(track_points_all[i + 1]).__copy__()
                next_pos = point_position(track_points_all[i + 1]).__copy__()
                point.replace(point_time(point), next_time)
                point.append(next_pos)
            except (AttributeError, IndexError, TypeError):
                next_time = point_time(track_points_all[i - 1]).__copy__()
                next_pos = point_position(track_points_all[i - 1]).__copy__()
                point.replace(point_time(point), next_time)
                point.append(next_pos)

    def get_stats(tcx_root):
        """
        :param etree._Element tcx_root: root element of tcx file
        :rtype: dict[str, etree._Element]
        """
        tts = tcx_root.find(add_ns('.//Lap/TotalTimeSeconds', default_ns))
        header_values = dict()
        for _tag in header_tags:
            header_values[_tag] = tcx_root.find(add_ns('.//Lap/{0}'.format(_tag), default_ns))
        return header_values

    stats1 = get_stats(file1_root)
    stats2 = get_stats(file2_root)
    header = dict()

    def text(_el):
        if _el is None:
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

    def strp_dif_formats(_time):
        try:
            res = calendar.timegm(time.strptime(_time, time_format))
        except ValueError:
            res = calendar.timegm(time.strptime(_time, time_format2))
        return res

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

    def get_point_time(point):
        """
        :param etree._Element point:
        :rtype: int
        """
        _time = point.find(add_ns('./Time', default_ns)).text
        seconds = strp_dif_formats(_time)
        return seconds

    lap_path = add_ns('.//Lap', default_ns)
    lap_time = min(get_lap_time(file1_root.find(lap_path)), get_lap_time(file2_root.find(lap_path)))
    activity_id = format_time(get_point_time(track_points_all[0]) - 60)  # not duplicating activity in strava
    lap_start = format_time(lap_time)

    head = []
    for h in header:
        el = etree.Element(h)
        el.text = header[h]
        if el.tag not in ('MaximumHeartRateBpm', 'AverageHeartRateBpm'):
            head.append(el)

    head.extend(track_points_all)

    e = ElementMaker(nsmap=file1_root.nsmap, namespace=default_ns)

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

    basic = etree.tostring(basic, pretty_print=False, encoding="UTF-8", xml_declaration=True).replace('xsi:type',
                                                                                                      'type')

    with open(out_file, 'w+') as o:
        o.write(basic)


def parse_args():
    from argparse import ArgumentParser
    ap = ArgumentParser(description='merging 2 tcx files just sorting their tags')
    ap.add_argument('file1')
    ap.add_argument('file2')
    return ap.parse_args()


if __name__ == '__main__':
    args = parse_args()
    merge(file1=args.file1, file2=args.file2)
