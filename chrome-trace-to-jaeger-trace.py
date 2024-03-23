#!/usr/bin/env python3

import json
import argparse
import time


def normalize_chrome_trace(input_chrome_trace, option):
    output_normalized_chrome_trace = input_chrome_trace.copy()
    normalized_trace_events = []
    for i, event in enumerate(input_chrome_trace['traceEvents']):
        if 'ph' not in event:
            print(
                '[warning] There is no "ph" field at ".traceEvents[{}]"'.format(i))
            continue
        if event['ph'] == 'X':
            trace_event_b = event.copy()
            trace_event_b['ph'] = 'B'
            del trace_event_b['dur']
            trace_event_e = event.copy()
            trace_event_e['ph'] = 'E'
            trace_event_e['ts'] = event['ts'] + event['dur']
            del trace_event_e['dur']
            normalized_trace_events.append(trace_event_b)
            normalized_trace_events.append(trace_event_e)
        elif event['ph'] in ['B', 'E']:
            normalized_trace_events.append(event.copy())
        else:
            print(
                '[warning] There is no implementation of ".traceEvents[{}].ph": "{}"'.format(
                    i, event['ph']))
            continue

    sort_function = (lambda x: x['ts'])
    if option['broken-trace']:
        sort_function = (
            lambda x: (
                x['ph'],
                x['ts'] if x['ph'] == 'B' else -
                x['ts']))
    normalized_trace_events = sorted(
        normalized_trace_events,
        key=sort_function)
    output_normalized_chrome_trace['traceEvents'] = normalized_trace_events
    return output_normalized_chrome_trace


def convert_chrome_trace_to_jaeger(
        input_chrome_trace_file, output_jaeger_trace_file, option):
    with open(input_chrome_trace_file, 'r') as f:
        chrome_trace_data = json.load(f)

    chrome_trace_data = normalize_chrome_trace(chrome_trace_data, option)
    data = []
    process_map = {}
    for event in chrome_trace_data['traceEvents']:
        process_key = 'pid({})-tid({})'.format(event['pid'], event['tid'])
        process_map.setdefault(process_key, []).append(event)

    span_index = 0
    processes = {}
    spans = []
    span_children_map = {}
    trace_id = str(hex(int(time.time() * 1000)))[-7:]  # unixtimestamp[ms]
    for process_key, events in process_map.items():
        event_stack = []
        for event in events:
            if event['ph'] == 'B':
                span_id = "span:{}".format(str(span_index))
                event_stack.append((span_id, event))
                span_index += 1
                continue
            assert len(event_stack) > 0, 'len(evene_stack) must be more than 0'
            assert event['ph'] == 'E', '"ph" is expected to be "E": {}'.format(
                event)
            (span_id, pre_event) = event_stack[-1]
            if not option['broken-trace']:
                assert event['name'] == pre_event['name'], 'pre_event["name"] must be {}: {}\nIf the input file is broken trace file, please add "-b" flag.'.format(
                    event['name'], pre_event)
            event_stack.pop()
            startTime = pre_event['ts']
            endTime = event['ts']
            duration = endTime - startTime

            references = []
            childSpanIds = []
            if not option['without-hierarchy']:
                if len(event_stack) > 0:
                    (parent_span_id, _) = event_stack[-1]
                    reference = {
                        "refType": "CHILD_OF",
                        "traceID": trace_id,
                        "spanID": parent_span_id,
                    }
                    references = [reference]
                    span_children_map.setdefault(
                        parent_span_id, []).append(span_id)
                if span_id in span_children_map:
                    childSpanIds = span_children_map[span_id]
            hasChildren = len(childSpanIds) > 0
            span_data = {
                "traceID": trace_id,
                "spanID": span_id,
                "operationName": event['name'],
                "references": references,
                "startTime": startTime,  # us
                "duration": duration,  # us
                "tags": [
                    # {
                    # "key": "int value",
                    # "type": "int64",
                    # "value": 1234
                    # },
                    # {
                    # "key": "string value",
                    # "type": "string",
                    # "value": "hello"
                    # }
                ],
                "logs": [],
                "processID": process_key,
                "warnings": [],
                "process": {},
                "relativeStartTime": 0,
                "depth": 0,
                "hasChildren": hasChildren,
                "childSpanIds": childSpanIds,
            }
            spans.append(span_data)
        event = events[0]
        pid = event['pid']
        tid = event['tid']
        processes[process_key] = {
            "serviceName": process_key,
            "tags": [
                {
                    "key": "pid",
                    "type": "int64",
                    "value": pid,
                },
                {
                    "key": "tid",
                    "type": "int64",
                    "value": tid,
                },
            ]}
    trace = {
        "traceID": trace_id,
        "spans": spans,
        "processes": processes,
        "warnings": None,
    }
    data.append(trace)

    with open(output_jaeger_trace_file, 'w') as f:
        json.dump({
            "data": data,
        }, f, indent=4)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-o', '--output-filepath', default='/dev/stdout')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument(
        '-b',
        '--broken-trace',
        action='store_true',
        help='Input file trace is broken (parent-child relationship cannot be obtained correctly) (The input order is used as the parent-child relationship.)')
    parser.add_argument(
        '--without-hierarchy',
        action='store_true',
        help='Do not include parent-child relationship information in output files')
    parser.add_argument('input_filepath')
    parser.add_argument('args', nargs='*')

    args, extra_args = parser.parse_known_args()
    option = {
        'broken-trace': args.broken_trace,
        'without-hierarchy': args.without_hierarchy,
    }
    convert_chrome_trace_to_jaeger(
        args.input_filepath,
        args.output_filepath, option)


if __name__ == '__main__':
    main()
