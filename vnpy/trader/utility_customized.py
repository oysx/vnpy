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


class Shape(object):
    def __init__(self, data: np.ndarray, range: tuple = None, params: dict = None):
        self.data = data
        self.range = range if range is not None else (0, len(data))
        self.min, self.max = self.range
        self.params = params if params else {}
        self.found = set()

    def count(self):
        return len(self.found)

    def show(self):
        print(self.__class__.__name__, self.count(), self.found)


class Peak(Shape):
    def __init__(self, *args, **kwargs):
        super(Peak, self).__init__(*args, **kwargs)
        self.width = self.params.get("width", 5)
        self.percent = self.params.get("percent", 0.001)

    def foreach(self, *args, **kwargs):
        raise NotImplementedError("")

    def find(self, *args, **kwargs):
        raise NotImplementedError("")


class PeakHorizontalSymmetry(Peak):
    def foreach(self, positive: bool = True):
        anchor = None
        for ix in range(*self.range):
            d = self.data[ix]

            if anchor is None or (positive and self.data[anchor] < d) or (not positive and self.data[anchor] > d):
                anchor = ix
                continue
            if ix - anchor == self.width:
                prev = anchor - self.width if anchor >= self.width else 0
                self.found.add(anchor)
                yield anchor, (prev, ix+1)
                anchor = None   # Want to find all shape not only upper or lower shape


class PeakHorizontalAsymmetry(Peak):
    def __init__(self, *args, **kwargs):
        super(PeakHorizontalAsymmetry, self).__init__(*args, **kwargs)
        self.width_min = self.params.get("width_min", 3)
        self.width *= 2     # convert the width concept

    def foreach(self, positive: bool = True):
        for ix in range(*self.range):
            data: np.ndarray = self.data[ix:ix+self.width]
            peak = data.argmax().astype(int) if positive else data.argmin().astype(int)
            if self.width_min <= peak <= self.width - self.width_min:
                self.found.add(ix+peak)
                yield ix + peak, (ix, ix + self.width)







class PeakVerticalMean(Peak):
    def find(self, peak, range=None):
        min, max = range if range else (self.min, self.max)
        result = False
        left: np.ndarray = self.data[min:peak]
        right: np.ndarray = self.data[peak+1:max]
        left_mean = left.mean()
        right_mean = right.mean()
        left_percent = Algorithm.percent(left_mean, self.data[peak])
        right_percent = Algorithm.percent(right_mean, self.data[peak])
        if left_percent >= self.percent and right_percent >= self.percent:       # top
            result = True
        elif left_percent <= -self.percent and right_percent <= -self.percent:   # buttom
            result = True

        if result:
            self.found.add(peak)
        return result


class PeakVerticalSlope(Peak):
    def find(self, peak: int, range: tuple = None):
        min, max = range if range else (self.min, self.max)
        result = False
        left: np.ndarray = self.data[min:peak + 1]
        right: np.ndarray = self.data[peak:max]
        left = Algorithm.get_socpe(left, self.data[peak])
        right = Algorithm.get_socpe(right, self.data[peak])
        revert_percent = 1.0 - self.percent
        if left > revert_percent and right < self.percent:  # top
            result = True
        elif left < self.percent and right > revert_percent:  # buttom
            result = True

        if result:
            self.found.add(peak)
        return result


class PeakVerticalRatio(Peak):
    def __init__(self, *args, **kwargs):
        super(PeakVerticalRatio, self).__init__(*args, **kwargs)
        self.percent = self.params.get("percent", 0.1)

    def find(self, peak: int, range: tuple = None):
        min, max = range if range else (self.min, self.max)
        result = False
        left: np.ndarray = self.data[min:peak + 1]
        right: np.ndarray = self.data[peak:max]
        left = Algorithm.ratio_pos_neg(left)
        right = Algorithm.ratio_pos_neg(right)
        revert_percent = 1.0 - self.percent
        if left > revert_percent and right < self.percent:      # UP
            result = True
        elif left < self.percent and right > revert_percent:    # DOWN
            result = True

        if result:
            self.found.add(peak)
        return result


class Points(object):
    def __init__(self, data: np.ndarray):
        self.source = data
        self.array = np.zeros(len(data))

    def set(self, idx, positive=True):
        self.array[idx] = self.source[idx] if positive else -self.source[idx]

    def positive(self):
        return self.array * (self.array > 0)

    def negative(self):
        return -self.array * (self.array < 0)

    def all(self):
        return self.positive() - self.negative()


class ShapeFinder(object):
    def __init__(self, array_manager: ArrayManager):
        self.array_manager = array_manager
        self.high = array_manager.high

    def search(self):
        alternative_points = Points(self.high)
        peak_points = Points(self.high)
        peaks = PeakHorizontalAsymmetry(data=self.high, params={"width": 8})
        more = PeakVerticalRatio(data=self.high)
        for anchor, range in peaks.foreach(positive=True):
            alternative_points.set(anchor, positive=True)
            if more.find(anchor, range):
                peak_points.set(anchor, positive=True)
        peaks.show()
        more.show()

        peaks = PeakHorizontalAsymmetry(data=self.high, params={"width": 6})
        more = PeakVerticalRatio(data=self.high)
        for anchor, range in peaks.foreach(positive=False):
            alternative_points.set(anchor, positive=False)
            if more.find(anchor, range):
                peak_points.set(anchor, positive=False)
        peaks.show()
        more.show()

        strategy = Strategy(self.high, peak_points)
        break_point, key_point = strategy.find_break()
        return alternative_points, peak_points.positive(), peak_points.negative(), break_point, key_point


class Strategy(object):
    def __init__(self, data: np.ndarray, points: np.ndarray, params: dict = None):
        self.data = data
        self.points = points
        self.params = params if params else {}
        self.percent: float = self.params.get("percent", 0.001)

        self.break_through_points = Points(self.data)
        self.key_points = Points(self.data)
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
            self.key_points.set(self.kp_up)
        else:  # UP
            self.state = Strategy.State.STATE_BREAK_UP
            result = self.break_up
            # update self.kp_down to lowest point between self.kp_up and self.break_up
            self.kp_down = self.kp_up + self.data[self.kp_up:self.break_up].argmin()
            self.break_down = self.get_break_point(self.kp_down, ix, False)
            self.key_points.set(self.kp_down, positive=False)

        if result is not None:
            self.break_through_points.set(result, result == self.break_up)
            # print(self.state)

    def find_break(self):
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
                self.key_points.set(ix)
            elif not self.kp_down and self.points[ix] < 0:
                self.kp_down = ix
                self.key_points.set(ix, positive=False)

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
                self.key_points.set(ix)
            elif self.state == Strategy.State.STATE_BREAK_DOWN and self.points[ix] < 0 and self.data[ix] < self.data[self.kp_down] * (1 - self.percent):
                self.kp_down = ix
                self.key_points.set(ix, positive=False)

            if self.state == Strategy.State.STATE_BREAK_UP and self.points[ix] < 0 or self.state == Strategy.State.STATE_BREAK_DOWN and self.points[ix] > 0:
                continue

            # Here we start state machine
            self.break_up = self.get_break_point(self.kp_up, ix, True)
            self.break_down = self.get_break_point(self.kp_down, ix, False)

            if self.break_down < self.break_up:
                self.break_action(False, ix)
            elif self.break_down > self.break_up:
                self.break_action(True, ix)

        return self.break_through_points, self.key_points
