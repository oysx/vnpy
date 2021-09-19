import traceback
from .utility import ArrayManager
import numpy as np
import sys


def is_self(self):
    for tb in traceback.walk_stack(None):
        caller = tb[0].f_locals.get("self")
        if caller and caller is self:
            print("Execute custom")
            return True
    else:
        print("Skip custom")
        return False


class WrapIt(object):
    def __init__(self, cls, name, func):
        self.cls = cls
        self.name = name
        self.func = func
        self.origin = getattr(cls, name)
        self.origin = self.origin

    def wrap(self):
        def origin(*args, **kwargs):
            self.func(*args, **kwargs)
            return self.origin(*args, **kwargs)

        return origin

    def __enter__(self):
        setattr(self.cls, self.name, self.wrap())
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        setattr(self.cls, self.name, self.origin)
        pass


class Shape(object):
    def __init__(self, data: np.ndarray, range: tuple = None, params: dict = None):
        self.data = data
        self.range = range if range is not None else (0, len(data))
        self.min, self.max = self.range
        self.params = params if params else {}


class Peak(Shape):
    def __init__(self, *args, **kwargs):
        super(Peak, self).__init__(*args, **kwargs)
        self.width = self.params.get("width", 5)
        self.percent = self.params.get("percent", 0.001)

    def foreach(self, *args, **kwargs):
        raise NotImplementedError("")

    def find(self, *args, **kwargs):
        raise NotImplementedError("")


class PeakWeak(Peak):
    def foreach(self, positive: bool = True):
        anchor = None
        for ix in range(*self.range):
            d = self.data[ix]

            if anchor is None or (positive and self.data[anchor] < d) or (not positive and self.data[anchor] > d):
                anchor = ix
                continue
            if ix - anchor == self.width:
                prev = anchor - self.width if anchor >= self.width else 0
                yield anchor, (prev, ix+1)
                anchor = None   # Want to find all shape not only upper or lower shape


class PeakNonSymmetry(Peak):
    def __init__(self, *args, **kwargs):
        super(PeakNonSymmetry, self).__init__(*args, **kwargs)
        self.width_min = self.params.get("width_min", 3)
        self.width *= 2     # convert the width concept

    def foreach(self, positive: bool = True):
        for ix in range(*self.range):
            data: np.ndarray = self.data[ix:ix+self.width]
            peak = data.argmax().astype(int) if positive else data.argmin().astype(int)
            if self.width_min <= peak <= self.width - self.width_min:
                yield ix + peak, (ix, ix + self.width)


def get_percent(data: float, peak: float):
    return (peak - data) / peak


def delta(data: np.ndarray):
    length = len(data)
    if not length:
        return np.zeros(0)
    ret = np.zeros(length - 1)
    for i in range(length - 1):
        ret[i] = data[i + 1] - data[i]
    return ret


def get_socpe(data: np.ndarray, whole):
    data = delta(data)
    data = data.sum()
    # data = data > 0
    # data = data.sum() / len(data)
    data = data / whole if data > 0 else (whole + data) / whole
    return data


class PeakMean(Peak):
    def find(self, peak):
        left: np.ndarray = self.data[self.min:peak]
        right: np.ndarray = self.data[peak+1:self.max]
        left_mean = left.mean()
        right_mean = right.mean()
        left_percent = get_percent(left_mean, self.data[peak])
        right_percent = get_percent(right_mean, self.data[peak])
        if left_percent >= self.percent and right_percent >= self.percent:       # top
            return True
        elif left_percent <= -self.percent and right_percent <= -self.percent:   # buttom
            return True
        return False


class PeakSlope(Peak):
    def find(self, peak: int):
        left: np.ndarray = self.data[:peak + 1]
        right: np.ndarray = self.data[peak:]
        left = get_socpe(left, self.data[peak])
        right = get_socpe(right, self.data[peak])
        revert_percent = 1.0 - self.percent
        if left > revert_percent and right < self.percent:  # top
            return True
        elif left < self.percent and right > revert_percent:  # buttom
            return True
        return False


class ShapeFinder(object):
    def __init__(self, array_manager: ArrayManager):
        self.array_manager = array_manager
        self.high = array_manager.high

    def search(self):
        peak_points = np.zeros(len(self.high))
        top_point = np.zeros(len(self.high))
        buttom_point = np.zeros(len(self.high))
        peaks = PeakNonSymmetry(data=self.high, params={"width": 8})
        for anchor, range in peaks.foreach(positive=True):
            peak_points[anchor] = self.high[anchor]
            more = PeakMean(data=self.high, range=range)
            if more.find(anchor):
                top_point[anchor] = self.high[anchor]
                # print("Found top: ", anchor)

        peaks = PeakNonSymmetry(data=self.high, params={"width": 6})
        for anchor, range in peaks.foreach(positive=False):
            peak_points[anchor] = -self.high[anchor]
            more = PeakMean(data=self.high, range=range)
            if more.find(anchor):
                buttom_point[anchor] = self.high[anchor]
                # print("Found buttom: ", anchor)

        strategy = Strategy(self.high, top_point-buttom_point)
        break_point, key_point = strategy.find_break()
        return peak_points, top_point, buttom_point, break_point, key_point


class Strategy(object):
    def __init__(self, data: np.ndarray, points: np.ndarray, params: dict = None):
        self.data = data
        self.points = points
        self.params = params if params else {}
        self.percent: float = self.params.get("percent", 0.001)

        self.breaks = np.zeros(len(self.data))
        self.kp_array = np.zeros((len(self.data), 2))
        self.kp_up = None
        self.kp_down = None
        self.break_up = None
        self.break_down = None
        self.state = None

    class State(object):
        STATE_BREAK_UP = "Break Up"
        STATE_BREAK_DOWN = "Break Down"

    def get_break_point(self, key_point: int, ix: int, direction: bool):
        if direction:  # UP
            _break_point = ix + np.nonzero(self.data[ix:] > self.data[key_point] * (1 + self.percent))[0]
            _break_point = _break_point[0] if len(_break_point) > 0 else sys.maxsize
        else:  # DOWN
            _break_point = ix + np.nonzero(self.data[ix:] < self.data[key_point] * (1 - self.percent))[0]
            _break_point = _break_point[0] if len(_break_point) > 0 else sys.maxsize
        return _break_point

    def break_action(self, direction: bool, ix):
        if not direction:  # DOWN
            self.state = Strategy.State.STATE_BREAK_DOWN
            result = self.break_down
            # update self.kp_up to highest point between self.kp_down and self.break_down
            self.kp_up = self.kp_down + self.data[self.kp_down:self.break_down].argmax()
            self.break_up = self.get_break_point(self.kp_up, ix, True)
            self.kp_array[self.kp_up][0] = self.data[self.kp_up]
            self.kp_array[self.kp_up][1] = 1
        else:  # UP
            self.state = Strategy.State.STATE_BREAK_UP
            result = self.break_up
            # update self.kp_down to lowest point between self.kp_up and self.break_up
            self.kp_down = self.kp_up + self.data[self.kp_up:self.break_up].argmin()
            self.break_down = self.get_break_point(self.kp_down, ix, False)
            self.kp_array[self.kp_down][0] = self.data[self.kp_down]
            self.kp_array[self.kp_down][1] = -1

        if result is not None:
            self.breaks[result] = self.data[result] if result == self.break_up else -self.data[result]
            # print(self.state)

    def find_break(self):
        self.breaks = np.zeros(len(self.data))
        self.kp_array = np.zeros((len(self.data), 2))

        self.kp_up = None
        self.kp_down = None
        self.break_up = None
        self.break_down = None
        self.state = None
        iteration = iter(self.points.nonzero()[0])

        skip = False
        while True:
            try:
                ix = ix if skip else next(iteration)
                skip = False
            except StopIteration:
                break

            if not self.kp_up and self.points[ix] > 0:
                self.kp_up = ix
                self.kp_array[ix][0] = self.data[ix]
                self.kp_array[ix][1] = 1
            elif not self.kp_down and self.points[ix] < 0:
                self.kp_down = ix
                self.kp_array[ix][0] = self.data[ix]
                self.kp_array[ix][1] = -1

            if self.kp_up is None or self.kp_down is None:
                continue

            if self.break_down and ix < self.break_down and self.break_up and ix < self.break_up:
                # In the middle of the self.break_up/down, these points are not concerned
                continue

            if self.break_down and self.break_down < ix and self.state == Strategy.State.STATE_BREAK_UP:
                self.break_action(False, ix)
                skip = True
                continue
            elif self.break_up and self.break_up < ix and self.state == Strategy.State.STATE_BREAK_DOWN:
                self.break_action(True, ix)
                skip = True
                continue

            if self.state == Strategy.State.STATE_BREAK_UP and self.points[ix] > 0 and self.data[ix] > self.data[self.kp_up] * (1 + self.percent):
                # update self.kp_up
                self.kp_up = ix
                self.kp_array[ix][0] = self.data[ix]
                self.kp_array[ix][1] = 1
            elif self.state == Strategy.State.STATE_BREAK_DOWN and self.points[ix] < 0 and self.data[ix] < self.data[self.kp_down] * (1 - self.percent):
                self.kp_down = ix
                self.kp_array[ix][0] = self.data[ix]
                self.kp_array[ix][1] = -1

            if self.state == Strategy.State.STATE_BREAK_UP and self.points[ix] < 0 or self.state == Strategy.State.STATE_BREAK_DOWN and self.points[ix] > 0:
                continue

            # Here we start state machine
            self.break_up = self.get_break_point(self.kp_up, ix, True)
            self.break_down = self.get_break_point(self.kp_down, ix, False)

            if self.break_down < self.break_up:
                self.break_action(False, ix)
            elif self.break_down > self.break_up:
                self.break_action(True, ix)

        return self.breaks, self.kp_array
