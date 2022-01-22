import math
from math import ceil, nan
from subprocess import call
from turtle import st
import numpy as np
import json
import sys

class Algorithm(object):
    @staticmethod
    def percent(data: float, peak: float):
        return (peak - data) / peak

    @staticmethod
    def ratio_pos_neg(data: np.ndarray):
        data = Algorithm.derivative(data)
        positive: np.ndarray = data * (data > 0)
        negative: np.ndarray = data * (data < 0)
        return positive.sum() / (positive.sum() - negative.sum())

    @staticmethod
    def derivative(data: np.ndarray):
        length = len(data)
        if not length:
            return np.zeros(0)
        ret = np.zeros(length)
        ret[0] = 0.0
        for i in range(1, length):
            ret[i] = data[i] - data[i - 1]
        return ret

    @staticmethod
    def get_socpe(data: np.ndarray, whole):
        data = Algorithm.derivative(data)
        data = data.sum()
        # data = data > 0
        # data = data.sum() / len(data)
        data = data / whole if data > 0 else (whole + data) / whole
        return data


class ViNone(object):
    def __add__(self, other):
        return self

    def __radd__(self, other):
        return self

    def __truediv__(self, other):
        return self

    def __round__(self, length):
        return self

    def __str__(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return self.__class__.__name__

    def __lt__(self, other):
        return True

    def __gt__(self, other):
        return False

class ViData(object):
    def __init__(self) -> None:
        super().__init__()
        self.data = []

        self.base = 0   # real array start offset on virtual space
        self.count = 0  # real array end offset on virtual space

        self.cursor = 0 # new incoming data start offset on virtual space
        self.ending = 0 # last end offset on virtual space

    def add(self, data):
        self.data.append(data)
        self.count += 1

    def update(self, data: list):
        self.data += data
        self.count += len(data)

    def refresh(self):
        self.cursor = self.ending
        self.ending = self.count

    def has_incoming(self):
        return self.ending > self.cursor

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.data[key - self.base]
        elif isinstance(key, slice):
            start = key.start - self.base
            stop = key.stop if key.stop is not None else self.count
            stop = stop - self.base
            return self.data[start:stop:key.step]

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.data[key - self.base] = value

    def shift(self, offset):
        self.base += offset
        self.data = self.data[offset:]

    @property
    def physical_cursor(self):
        return self.cursor - self.base

    @property
    def physical_data(self):
        return self.data

    @property
    def length(self):   # virtual length
        return self.count

    @property
    def physical_length(self):  # physical length
        return len(self.data)

    @property
    def real_length(self):  # virtual length minus prefix ViNone(s)
        ignore = 0
        total = len(self.data)
        while total > ignore and (isinstance(self.data[ignore], ViNone) or math.isnan(self.data[ignore])):
            ignore += 1

        return self.count - ignore


class ViReflect(object):
    def __new__(cls, *args, **kwargs):
        instance = super(ViReflect, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        instance = type(cls.__name__, (object,), {"v": instance})()
        return instance

    def __init__(self, callback=None, init_value=None):
        self.callback = callback
        self._value = init_value

    def __set__(self, instance, value):
        self._value = value
        if self.callback:
            self.callback(value)

    def __get__(self, instance, owner):
        if not instance:
            return self
        return self._value

    def __delete__(self, instance):
        pass


class ViLayer(object):
    DEBUG = False
    FLOAT_MAX = float("inf")
    FLOAT_MIN = -float("inf")

    # global data used by all sub-class instances
    g = type("Anonymous", (object,), {
        'force_propagate': True,
    })()

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.input: ViData = None
        self.reference: ViData = None
        self.output = ViData()
        self.others = ViData()
        self.children = []
        self.show = kwargs.get("show", False)

    def update(self):
        self.output.refresh()

        if not self.g.force_propagate and not self.output.has_incoming():
            # Don't propagate downstream if not new data available
            return

        if self.show or self.DEBUG:
            print("***(%s): output=%s, cursor=%s" % (self.__class__.__name__, self.output.physical_data, self.output.physical_cursor))

        for child in self.children:
            child.update()

    def shift(self, offset):
        self.output.shift(offset)
        for child in self.children:
            child.shift(offset)

    def set_reference(self, ref):
        self.reference = ref.output

    @staticmethod
    def connect(layers: list):
        ViLayer.g.layers = layers

        for i in range(len(layers)-1):
            layers[i].children += [layers[i+1]]
            layers[i+1].input = layers[i].output

        for layer in layers:
            layer.pre_run()

    def pre_run(self):
        pass

    def get_layers(self, cls_type=None):
        return [layer for layer in self.g.layers if (not cls_type) or isinstance(layer, cls_type)]

class ViLayerData(ViLayer):
    def update(self, data: list = None):
        if data is None:
            self.output.update(self.input.data[self.input.cursor:])
        else:
            self.output.update(data if isinstance(data, list) else [data])
        return super().update()


class ViLayerSMA(ViLayer):
    def __init__(self, width: int=3, **kwargs) -> None:
        super().__init__(**kwargs)
        self.width = width

    def update(self):
        padding = self.width - 1 - self.input.cursor
        data = [ViNone()] * padding + self.input.data if padding > 0 else self.input.data
        cursor = self.input.cursor + padding if padding > 0 else self.input.cursor

        for i in range(cursor, len(data)):
            result = sum(data[i+1-self.width : i+1]) / self.width
            # result = round(result, 1)
            self.output.add(result)

        super().update()

    def get_offset(self):
        return self.width -1


class ViLayerShift(ViLayer):
    def __init__(self, cls, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cls = cls
        self.offset = 0

    def pre_run(self):
        for layer in self.get_layers(cls_type=self.cls):
            if layer == self:
                # just collect layers before me
                break
            if hasattr(layer, "get_offset"):
                self.offset += layer.get_offset()

    def update(self):
        for i in range(self.input.cursor, self.input.length):
            data = self.input[i]
            self.output.add((self.compensate(data[0], data[1]), data[1]))

        super().update()

    def compensate(self, off, up_down):
        mmx = off
        for i in range(off-4, off):
            if up_down and self.reference[i] > self.reference[mmx]:
                mmx = i
            elif (not up_down) and self.reference[i] < self.reference[mmx]:
                mmx = i
        return mmx


class ViLayerPeakHorizontalAsymmetry(ViLayer):
    def __init__(self, width: int=10, edge: int=3, **kwargs) -> None:
        super().__init__(**kwargs)
        self.width = width
        self.edge = edge
        self.off_max = -1
        self.off_min = -1
        self.off_start = -1

    def _max(self):
        maximum = ViLayer.FLOAT_MIN

        for i in range(self.off_start, self.off_start+self.width):
            if self.reference[i] > maximum:
                maximum = self.reference[i]
                self.off_max = i

    def _min(self):
        minimum = ViLayer.FLOAT_MAX

        for i in range(self.off_start, self.off_start+self.width):
            if self.reference[i] < minimum:
                minimum = self.reference[i]
                self.off_min = i

    def find(self, off_peak, is_max):
        offset = self.off_start
        # print("--%s:%d(%d,%d)" % ("MAX" if is_max else "MIN", off_peak, offset, offset+self.width))
        if off_peak >= offset + self.edge and off_peak <= offset + self.width - self.edge:
            self.output.add((off_peak, (offset, offset + self.width), is_max))

    def search(self, offset):
        for i in range(offset, self.reference.length):
            self.off_start += 1
            if self.off_max < self.off_start:
                self._max()
            if self.off_min < self.off_start:
                self._min()

            if self.reference[i] > self.reference[self.off_max]:
                self.off_max = i
            if self.reference[i] < self.reference[self.off_min]:
                self.off_min = i

            self.find(self.off_min, False)
            self.find(self.off_max, True)

    def update(self):
        if self.off_start < 0:
            length = self.reference.real_length
            if length >= self.width:
                self.off_start = self.reference.length - length - 1
                cursor = self.off_start + self.width
                self.search(cursor)
        else:
            self.search(self.reference.cursor)

        return super().update()


class ViLayerPeakVerticalRatio(ViLayer):
    def __init__(self, width: int=10, percentage: float=0.1, **kwargs) -> None:
        super().__init__(**kwargs)
        self.width = width
        self.percentage = percentage

    def find(self, element):
        peak, range, up_down = element
        min, max = range
        result = False
        left: np.ndarray = np.array(self.reference[min:peak + 1])
        right: np.ndarray = np.array(self.reference[peak:max])
        left = Algorithm.ratio_pos_neg(left)
        right = Algorithm.ratio_pos_neg(right)
        revert_percent = 1.0 - self.percentage
        if left > revert_percent and right < self.percentage:      # UP
            result = True
        elif left < self.percentage and right > revert_percent:    # DOWN
            result = True

        if result and (self.output.length == 0 or self.output[-1][0] != peak):
            self.output.add((peak, up_down))

    def update(self):
        for i in range(self.input.cursor, self.input.length):
            self.find(self.input[i])

        super().update()


# Can't handle the edge case on "COUNT_FOR_KEYPOINT_EQ_BREAKPOINT=True"
class ViLayerBreakthrough(ViLayer):
    STATE_IDLE = "idle"
    STATE_START = "start"
    STATE_UP = "up"
    STATE_DOWN = "down"
    
    def __init__(self, percentage: float=0.001, **kwargs) -> None:
        super().__init__(**kwargs)
        self.percentage = percentage
        self.state = ViReflect(callback=self.on_state_change, init_value=self.STATE_IDLE)
        self.kp_up = ViReflect(callback=self.on_kp_up, init_value=None)
        self.kp_down = ViReflect(callback=self.on_kp_down, init_value=None)
        self.break_up = ViReflect(callback=self.on_break_through, init_value=None)
        self.break_down = ViReflect(callback=self.on_break_through, init_value=None)
        self.cursor = None

        self.show_change = True

        self.next_kp = None
        self.save_kp = None

    def show_variables(self):
        if self.show_change:
            pass
            # print("### %d %d %d %s" % (self.cursor-1, self.kp_up.v, self.kp_down.v, self.state.v))
        self.show_change = False

    def on_state_change(self, value):
        self.save_kp = None
        self.show_change = True

    def on_kp_up(self, value):
        self.threshold_up = self.reference[value] * (1 + self.percentage)
        self.show_change = True
        self.others.add((value, True))

    def on_kp_down(self, value):
        self.threshold_down = self.reference[value] * (1 - self.percentage)
        self.show_change = True
        self.others.add((value, False))

    def on_break_through(self, value):
        self.output.add(value)

    def supplement(self, start, end, up_down=True):
        data = self.reference[start:end]
        data = np.array(data)
        if up_down:
            result = start + data.argmax()
        else:
            result = start + data.argmin()
        
        result = int(result)
        return result

    def action_break_down(self):
        self.state.v = self.STATE_DOWN
        self.break_down.v = (self.cursor, False)
        self.kp_up.v = self.supplement(self.kp_down.v, self.cursor)

    def action_break_up(self):
        self.state.v = self.STATE_UP
        self.break_up.v = (self.cursor, True)
        self.kp_down.v = self.supplement(self.kp_up.v, self.cursor, False)

    def action_key_up(self):
        self.kp_up.v = self.cursor
        self.state.v = self.STATE_START

    def action_key_down(self):
        self.kp_down.v = self.cursor
        self.state.v = self.STATE_START

    def state_start(self):
        # search only break through
        if self.reference[self.cursor] < self.threshold_down:
            self.action_break_down()
        elif self.reference[self.cursor] > self.threshold_up:
            self.action_break_up()

    def state_up(self):
        # search break_down, point_up
        if self.reference[self.cursor] < self.threshold_down:
            # found break_down
            self.action_break_down()
        elif self.is_kp(True) and self.on_percent(True):
            # found point_up
            self.action_key_up()

    def state_down(self):
        # search break_up, point_down
        if self.reference[self.cursor] > self.threshold_up:
            # found break_up
            self.action_break_up()
        elif self.is_kp(False) and self.on_percent(False):
            # found point_down
            self.action_key_down()

    def on_percent(self, up_down):
        if up_down and self.reference[self.cursor] > self.threshold_up:
            return True
        elif (not up_down) and self.reference[self.cursor] < self.threshold_down:
            return True
        return False

    def is_kp(self, up_down):
        self.save_kp = self.save_kp if self.save_kp is not None else self.cursor

        while self.next_kp < self.input.length:
            data = self.input[self.next_kp]
            if self.cursor == data[0]:
                return data[1] == up_down
            elif self.cursor < data[0]:
                break

            if self.save_kp is not None and self.save_kp < data[0] and data[1] == up_down:
                # workaround for edge case
                self.cursor = data[0]   # go backward to restart check
                # self.next_kp += 1

                self.save_kp = None
                return True

            self.next_kp += 1
        
        return False

    def find(self):
        self.next_kp = self.input.cursor
        while self.cursor < self.reference.length:
            self.show_variables()
            getattr(self, "state_"+self.state.v)()

            self.cursor += 1

    def update(self):
        if self.cursor is None:
            # prepare initial condition
            for i in range(self.input.cursor, self.input.length):
                kp, up_down = self.input[i]
                if up_down:
                    self.kp_up.v = kp
                else:
                    self.kp_down.v = kp

                if self.kp_down.v is not None and self.kp_up.v is not None:
                    self.cursor = kp
                    self.state.v = self.STATE_START
                    break

        if self.cursor is not None:
            self.find()

        super().update()


def show_data(name, data):
    out = data
    out = [d[0] if isinstance(d, tuple) else d for d in out]
    out = list(set(out))
    out.sort()
    print("*"*5 + name + "*"*10)
    print(out)
    print(len(out))

def show_diff(a, b):
    a = set([d[0] if isinstance(d, tuple) else d for d in a])
    b = set([d[0] if isinstance(d, tuple) else d for d in b])
    print(a.difference(b), b.difference(a))

class ViFlow(object):
    def __init__(self) -> None:
        super().__init__()
        self.input = None
        self.output = None
        self.count = 0

    def run(self, data):
        self.input.update(data)
        output = self.output.output
        if self.count != output.length:
            self.count = output.length
            return output[output.cursor:]

    @property
    def result(self):
        return self.output.output.data

    @property
    def layers_result(self):
        layers = self.output.g.layers
        result = [layer.output.data for layer in layers]
        for layer in layers:
            if layer.others.length:
                result.append(layer.others.data)
        
        return result

    def setup(self, **kwargs):
        data = ViLayerData()
        l1 = ViLayerSMA()
        l2 = ViLayerSMA()
        horizontal = ViLayerPeakHorizontalAsymmetry()
        horizontal.set_reference(l2)
        vertical = ViLayerPeakVerticalRatio()
        vertical.set_reference(l2)
        compensate = ViLayerShift(ViLayerSMA)
        compensate.set_reference(data)
        finder = ViLayerBreakthrough()
        finder.set_reference(data)
        ViLayer.connect([data, l1, l2, horizontal, vertical, compensate, finder])
        
        self.input = data
        self.output = finder
        for k, v in kwargs.items():
            setattr(self.output.g, k, v)


def test(dd, **kwargs):
    flow = ViFlow()
    flow.setup(**kwargs)
    
    for i in dd[:]:
        # print("#" * 10)
        flow.run(i)
    
    layers = flow.layers_result
    candidate = layers[3]
    peak = layers[4]
    breaks = layers[6]
    keys = layers[7]

    return candidate, peak, breaks, keys

if __name__ == "__main__":
    with open("c:\\users\\yangs29\\data.json") as f:
        data = json.load(f)
    
    candidate, peak, breaks, keys = test(data)
    # show_data("candidates", candidate)
    # show_data("peak", peak)
    show_data("breaks", breaks)
    show_data("keys", keys)
    c,p,b,k = test(data, force_propagate=False)
    show_diff(candidate, c)
    show_diff(peak, p)
    show_diff(breaks, b)
    show_diff(keys, k)
