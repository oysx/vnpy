from gettext import find
import imp
import json
from vnpy.trader.utility_customized import Strategy, ShapeFinder, Incremental
import numpy as np

# Load historical data from json file
with open("data.json") as f:
    data = json.load(f)

data = np.array(data)
print(data)

finder = ShapeFinder(data)
alternative_points, peak_points, break_points, key_points = finder.search()
alternative_points = set(alternative_points.values().nonzero()[0].tolist())
peak_points = set(peak_points.values().nonzero()[0].tolist())
break_points = set(break_points.values().nonzero()[0].tolist())
key_points = set(key_points.values().nonzero()[0].tolist())

def calculate(other):
    count = 100
    save_point = None
    offset = 0
    for i in range(data.size - count):
        finder = ShapeFinder(data[i-offset:i+count], save_point=save_point)
        alternative_points, peak_points, break_points, key_points = finder.search(i-offset)
        peak = break_points.values().nonzero()[0] + i-offset
        peak = set(peak.tolist())
        other.update(peak)

        save_point = finder.save_data
        need_offset = any([v<=offset for v in save_point.values() if isinstance(v, int)])
        if need_offset:
            offset += 1
        else:
            for k,v in save_point.items():
                if not isinstance(v, int):
                    continue
                save_point[k] = v-1-offset
            offset = 0

dd = Incremental()
for i in range(data.size):
    d = dd.update(data[i])
    if d:
        print(i, d)

# calculate(other)

def compare(all, other):
    print("*****")
    print(len(other.intersection(all)))
    all = list(all)
    all.sort()
    print(len(all), all)
    other = list(other)
    other.sort()
    print(len(other), other)

compare(alternative_points, dd.alternative)
compare(peak_points, dd.peakpoint)
compare(break_points, dd.breakpoint)
compare(key_points, dd.keypoint)
