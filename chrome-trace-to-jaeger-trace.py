#!/usr/bin/env python3

import json
import argparse
import uuid


def normalize_chrome_trace(input_chrome_trace):
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
    normalized_trace_events = sorted(
        normalized_trace_events,
        key=lambda x: x['ts'])
    output_normalized_chrome_trace['traceEvents'] = normalized_trace_events
    return output_normalized_chrome_trace


def convert_chrome_trace_to_jaeger(
        input_chrome_trace_file, output_jaeger_trace_file):
    with open(input_chrome_trace_file, 'r') as f:
        chrome_trace_data = json.load(f)

    chrome_trace_data = normalize_chrome_trace(chrome_trace_data)
    data = []
    process_map = {}
    for event in chrome_trace_data['traceEvents']:
        process_key = 'pid({})-tid({})'.format(event['pid'], event['tid'])
        process_map.setdefault(process_key, []).append(event)

    span_index = 0
    processes = {}
    for process_key, events in process_map.items():
        event_stack = []
        spans = []
        for event in events:
            if event['ph'] == 'B':
                span_id = "span:{}".format(str(span_index))
                event_stack.append((span_id, event))
                span_index += 1
                continue
            assert len(event_stack) > 0, 'len(evene_stack) must be more than 0'
            assert event['ph'] == 'E', '"ph" is expected to be "E": {}'.format(
                event)
            trace_id = str(uuid.uuid1()).replace('-', '')
            (span_id, pre_event) = event_stack[-1]
            assert event['name'] == pre_event['name'], 'pre_event["name"] must be {}: {}'.format(
                event['name'], pre_event)
            event_stack.pop()
            startTime = pre_event['ts']
            endTime = event['ts']
            duration = endTime - startTime
            references = []
            if len(event_stack) > 0:
                (parent_span_id, _) = event_stack[-1]
                reference = {
                    "refType": "CHILD_OF",
                    "traceID": trace_id,
                    "spanID": parent_span_id,
                }
                references = [reference]
            span_data = {
                "traceID": trace_id,
                "spanID": span_id,
                "operationName": event['name'],
                "references": references,
                "startTime": startTime,  # us
                "duration": duration,  # ms
                "tags": [
                    {
                        "key": "int value",
                        "type": "int64",
                        "value": 1234
                    },
                    {
                        "key": "string value",
                        "type": "string",
                        "value": "hello"
                    }
                ],
                "logs": [],
                "processID": process_key,
                "warnings": [],
                "process": {},
                "relativeStartTime": 0,
                "depth": 0,
                "hasChildren": False,
                "childSpanIds": [
                ]
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
    parser.add_argument('input_filepath')
    parser.add_argument('args', nargs='*')

    args, extra_args = parser.parse_known_args()
    convert_chrome_trace_to_jaeger(
        args.input_filepath,
        args.output_filepath)


if __name__ == '__main__':
    main()
