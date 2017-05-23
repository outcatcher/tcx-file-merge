from __future__ import print_function
from lxml import etree
from lxml.builder import ElementMaker
import time
import calendar
import re
import logging
import os
from merger import add_ns


def time_seconds(_time):
    return calendar.timegm(time.strptime(_time, '%Y-%m-%dT%H:%M:%SZ'))


def time_formatted(seconds):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(seconds))


def add_breaks_to_timestamp(timestamp, _breaks_dict):
    """
    :param str timestamp:
    :param dict[int, int] _breaks_dict:
    :return: formatted timestamp with breaks added
    :rtype: str
    """
    sum_break = 0
    _time_seconds = time_seconds(timestamp)
    for _break in _breaks_dict:
        if _break <= _time_seconds:
            sum_break += _breaks_dict.get(_break)
    return time_formatted(_time_seconds + sum_break)


def interactive_extend(_file, _out_file):

    if not _out_file:
        _out_file = 'modified' + _file

    breaks = dict()
    date = ''
    for line in open(_file, 'r'):
        break_it = False
        for match in re.finditer("""<Id>(.+?)<""", line):
            date = time_seconds(match.group(1))
            break_it = True
        if break_it:
            break

    while True:
        local_time = raw_input('Break time from start (hours:minutes:seconds): ')
        if not local_time:
            break

        _s = [int(s) for s in local_time.split(':')]
        local_time_seconds = _s[0] * 60 * 60 + _s[1] * 60 + _s[2]
        local_time_seconds = date + local_time_seconds

        length_seconds = raw_input('Break length (minutes:seconds): ')
        if not length_seconds:
            break
        _l = [int(s) for s in length_seconds.split(':')]
        length_seconds = _l[0] * 60 + _l[1]

        breaks.update({local_time_seconds: length_seconds})

    tcx = etree.parse(_file)
    tcx_root = tcx.getroot()

    default_ns = """http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"""
    seconds_ns = """http://www.garmin.com/xmlschemas/ActivityExtension/v2"""
    maker = ElementMaker(nsmap=tcx_root.nsmap, namespace=default_ns)
    maker2 = ElementMaker(nsmap=tcx_root.nsmap, namespace=seconds_ns)

    def make_track_points(_tcx_root, _breaks_dict):
        """

        :param etree._Element _tcx_root:
        :param dict[int, int] _breaks_dict:
        :return:
        """
        source_track_points = _tcx_root.findall(add_ns('.//Trackpoint', default_ns))
        result_track_points = []
        for source_track_point in source_track_points:
            timestamp = source_track_point.find(add_ns('./Time', default_ns)).text
            result_track_point = maker.Trackpoint(
                maker.Time(
                    add_breaks_to_timestamp(timestamp, _breaks_dict)
                ),
                maker.AltitudeMeters(
                    source_track_point.find(add_ns('./AltitudeMeters', default_ns)).text
                ),
                maker.DistanceMeters(
                    source_track_point.find(add_ns('./DistanceMeters', default_ns)).text
                ),
                maker.HeartRateBpm(
                    maker.Value(source_track_point.find(add_ns('./HeartRateBpm/Value', default_ns)).text),
                    type='HeartRateInBeatsPerMinute_t'
                ),
                maker.Cadence(
                    source_track_point.find(add_ns('./Cadence', default_ns)).text
                ),
                maker.Extensions(
                    maker2.TPX(
                        maker2.Speed(
                            source_track_point.find(
                                add_ns('./Extensions', default_ns) + add_ns('/TPX/Speed', seconds_ns)).text
                        )
                    )
                )
            )
            result_track_points.append(result_track_point)
        return result_track_points

    tcx_res = maker.TrainingCenterDatabase(
        maker.Activities(
            maker.Activity(
                maker.Id(
                    tcx_root.find(add_ns('.//Activity/Id', default_ns)).text
                ),
                maker.Lap(
                    maker.Track(
                        *make_track_points(tcx_root, breaks)
                    ),
                    maker.TotalTimeSeconds(
                        tcx_root.find(add_ns('.//Lap/TotalTimeSeconds', default_ns)).text
                    ),
                    maker.DistanceMeters(
                        tcx_root.find(add_ns('.//Lap/DistanceMeters', default_ns)).text
                    ),
                    maker.MaximumSpeed(
                        tcx_root.find(add_ns('.//Lap/MaximumSpeed', default_ns)).text
                    ),
                    maker.Calories(
                        tcx_root.find(add_ns('.//Lap/Calories', default_ns)).text
                    ),
                    maker.Intensity(
                        tcx_root.find(add_ns('.//Lap/Intensity', default_ns)).text
                    ),
                    maker.AverageHeartRateBpm(
                        maker.Value(
                            tcx_root.find(add_ns('.//Lap/AverageHeartRateBpm/Value', default_ns)).text
                        ),
                        type='HeartRateInBeatsPerMinute_t'
                    ),
                    maker.MaximumHeartRateBpm(
                        maker.Value(
                            tcx_root.find(add_ns('.//Lap/MaximumHeartRateBpm/Value', default_ns)).text
                        ),
                        type='HeartRateInBeatsPerMinute_t'
                    ),
                    maker.Cadence(
                        tcx_root.find(add_ns('.//Lap/Cadence', default_ns)).text
                    ),
                    maker.TriggerMethod(
                        'Manual'
                    ),
                    StartTime=tcx_root.find(add_ns('.//Lap', default_ns)).attrib['StartTime']
                ),
                Sport='Biking'
            )
        )
    )

    with open(_out_file, 'w+') as o:
        o.write(etree.tostring(tcx_res, xml_declaration=True, pretty_print=True, encoding='UTF-8'))


if __name__ == '__main__':
    from argparse import ArgumentParser

    ap = ArgumentParser(description='Enlarge!')
    ap.add_argument('file')
    ap.add_argument('output')
    args = ap.parse_args()
    interactive_extend(_file=args.file, _out_file=args.output)
