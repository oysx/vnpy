import traceback
from .utility import ArrayManager
import numpy as np
import sys
import talib

COUNT_FOR_KEYPOINT_EQ_BREAKPOINT = True
COUNT_FOR_BREAK_FROM_KEYPOINT = True    # else for break from cursor


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
            if ix+self.width > self.range[1]:
                # Ignore edge points
                continue
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


class Transform(object):
    def __init__(self, *args, data: np.ndarray = None, **kwargs):
        self.data = data

    def get_contributor_range(self, range: tuple):
        return range

    def run(self):
        pass

    def get_data(self):
        return self.data


class TransformSMA(Transform):
    def __init__(self, *args, **kwargs):
        super(TransformSMA, self).__init__(*args, **kwargs)
        self.length = kwargs.get("length", 3)
        self.deep = kwargs.get("deep", 1)

    def get_contributor_range(self, range: tuple):
        prefix_length = (self.length - 1) * self.deep
        prefix_length = prefix_length if range[0] - prefix_length >= 0 else range[0]
        return range[0] - prefix_length, range[1]

    def run(self):
        for i in range(self.deep):
            self.data = talib.SMA(self.data, self.length)


class Points(object):
    def __init__(self, data: np.ndarray):
        self.source = data
        self.array = np.zeros(len(data))
        self.working = self.source
        self._indexes: list = []
        self.array_positive = None
        self.array_negative = None

    def set(self, idx, positive=True):
        self.working = self.array
        self.array[idx] = self.source[idx] if positive else -self.source[idx]

    def values(self):
        return self.working

    def indexes(self):
        if not len(self._indexes):
            self._indexes = self.working.nonzero()[0]
        return self._indexes

    def next(self, idx: int = None):
        self.indexes()

        if idx is None:
            return self._indexes[0]

        start = idx if COUNT_FOR_KEYPOINT_EQ_BREAKPOINT else idx+1
        if start >= len(self.working):
            return None

        last = self.working[start:].nonzero()[0]
        return start + last[0] if len(last) else None

    def positive(self):
        if self.array_positive is None:
            self.array_positive = self.working * (self.working > 0)
        return Points(self.array_positive)

    def negative(self):
        if self.array_negative is None:
            self.array_negative = -self.working * (self.working < 0)
        return Points(self.array_negative)

    def shift(self, func, data: np.ndarray):
        points = Points(data)
        positive = self.positive().indexes()
        for i in positive:
            i = func((i, i+1))
            i = data[i[0]:i[1]].argmax().astype(int) + i[0]
            points.set(i, True)

        negative = self.negative().indexes()
        for i in negative:
            i = func((i, i+1))
            i = data[i[0]:i[1]].argmin().astype(int) + i[0]
            points.set(i, False)

        return points


class PointPosition(object):
    def __new__(cls, *args, **kwargs):
        instance = super(PointPosition, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        instance = type(cls.__name__, (object,), {"v": instance})()
        return instance

    def __init__(self, recorder: Points, positive=True):
        self.recorder = recorder
        self.positive = positive
        self._value = None

    def __set__(self, instance, value):
        self._value = value
        self.recorder.set(value, positive=self.positive)

    def __get__(self, instance, owner):
        if not instance:
            return self
        return self._value

    def __delete__(self, instance):
        pass


class ShapeFinder(object):
    def __init__(self, data: np.ndarray, save_point: dict = None):
        self.data = data
        self.save_point = save_point
        self.save_data = {}

    def get_peaks(self, data: np.ndarray):
        alternative_points = Points(data)
        peak_points = Points(data)
        peaks = PeakHorizontalAsymmetry(data=data, params={"width": 5})
        more = PeakVerticalRatio(data=data)
        for anchor, range in peaks.foreach(positive=True):
            alternative_points.set(anchor, positive=True)
            if more.find(anchor, range):
                peak_points.set(anchor, positive=True)
        peaks.show()
        more.show()

        peaks = PeakHorizontalAsymmetry(data=data, params={"width": 6})
        more = PeakVerticalRatio(data=data)
        for anchor, range in peaks.foreach(positive=False):
            alternative_points.set(anchor, positive=False)
            if more.find(anchor, range):
                peak_points.set(anchor, positive=False)
        peaks.show()
        more.show()
        return alternative_points, peak_points

    def search(self, meta=0):
        sma2 = TransformSMA(data=self.data, length=3, deep=2)
        sma2.run()
        alternative_points, peak_points = self.get_peaks(sma2.get_data())
        alternative_points = alternative_points.shift(sma2.get_contributor_range, self.data)
        peak_points = peak_points.shift(sma2.get_contributor_range, self.data)

        strategy = Strategy(self.data, peak_points, save_point=self.save_point)
        break_point, key_point = strategy.find_break(meta)
        self.save_data = strategy.save_data
        return alternative_points, peak_points, break_point, key_point


class Strategy(object):
    def __init__(self, data: np.ndarray, points: Points, params: dict = None, save_point: dict = None):
        self.data = data
        self.points = points
        self.params = params if params else {}
        self.percent: float = self.params.get("percent", 0.001)

        self.key_points = Points(self.data)
        self.kp_up = PointPosition(self.key_points, positive=True)
        self.kp_down = PointPosition(self.key_points, positive=False)

        self.break_through_points = Points(self.data)
        self.break_up = PointPosition(self.break_through_points, positive=True)
        self.break_down = PointPosition(self.break_through_points, positive=False)

        self.state = None
        self.save_data = {}
        self.save_point = save_point if save_point else {}

    class State(object):
        STATE_BREAK_UP = "Break Up"
        STATE_BREAK_DOWN = "Break Down"

    def get_break_point(self, key_point: PointPosition, ix: int, direction: bool):
        if direction:  # UP
            _break_point = ix + np.nonzero(self.data[ix:] > self.data[key_point] * (1 + self.percent))[0]
            _break_point = _break_point[0] if len(_break_point) > 0 else sys.maxsize
        else:  # DOWN
            _break_point = ix + np.nonzero(self.data[ix:] < self.data[key_point] * (1 - self.percent))[0]
            _break_point = _break_point[0] if len(_break_point) > 0 else sys.maxsize
        return _break_point

    def supplement_point(self, start: int, end: int, positive=True):
        if positive:
            result = start + self.data[start:end].argmax()
        else:
            result = start + self.data[start:end].argmin()
        return result

    def is_break_through(self, data):
        return data != sys.maxsize

    def match_percent(self, base, check, positive=True):
        if positive:
            result = self.data[check] > self.data[base] * (1 + self.percent)
        else:
            result = self.data[check] < self.data[base] * (1 - self.percent)
        return result

    def action_break_through_down(self, value):
        self.state = Strategy.State.STATE_BREAK_DOWN
        self.break_down.v = value
        self.kp_up.v = self.supplement_point(self.kp_down.v, self.break_down.v, positive=True)
        return value

    def action_break_through_up(self, value):
        self.state = Strategy.State.STATE_BREAK_UP
        self.break_up.v = value
        self.kp_down.v = self.supplement_point(self.kp_up.v, self.break_up.v, positive=False)
        return value

    def action_keypoint_up(self, value):
        self.state = None
        self.kp_up.v = value
        return value

    def action_keypoint_down(self, value):
        self.state = None
        self.kp_down.v = value
        return value

    def find_break(self, meta=0):
        self.state = self.state if self.save_point.get("state") is None else self.save_point.get("state")

        self.save_data["cursor"] = None
        positive_points: Points = self.points.positive()
        negative_points: Points = self.points.negative()

        self.kp_up.v = positive_points.next() if self.save_point.get("kp_up") is None else self.save_point.get("kp_up")
        self.kp_down.v = negative_points.next() if self.save_point.get("kp_down") is None else self.save_point.get("kp_down")

        cursor = max(self.kp_up.v, self.kp_down.v) if self.save_point.get("cursor") is None else self.save_point.get("cursor")
        while cursor is not None:
            # print("^^^", meta, meta+cursor, meta+self.kp_up.v, meta+self.kp_down.v, self.state)

            self.save_data["cursor"] = int(cursor)
            # Here we start state machine
            break_up = self.get_break_point(self.kp_up.v, cursor, True)
            break_down = self.get_break_point(self.kp_down.v, cursor, False)
            next_point_up = positive_points.next(cursor)
            next_point_down = negative_points.next(cursor)
            if self.state == None:
                # search only break through
                if self.is_break_through(break_down) and break_down < break_up:
                    cursor = self.action_break_through_down(break_down)
                elif self.is_break_through(break_up) and break_up < break_down:
                    cursor = self.action_break_through_up(break_up)
                else:
                    cursor = None
            elif self.state == Strategy.State.STATE_BREAK_UP:
                # search break_down, point_up
                if next_point_up and next_point_up < break_down and self.match_percent(self.kp_up.v if COUNT_FOR_BREAK_FROM_KEYPOINT else cursor, next_point_up, positive=True):
                    cursor = self.action_keypoint_up(next_point_up)
                elif self.is_break_through(break_down):
                    cursor = self.action_break_through_down(break_down)
                else:
                    cursor = next_point_up+1 if COUNT_FOR_KEYPOINT_EQ_BREAKPOINT and next_point_up else next_point_up
            elif self.state == Strategy.State.STATE_BREAK_DOWN:
                # search break_up, point_down
                if next_point_down and next_point_down < break_up and self.match_percent(self.kp_down.v if COUNT_FOR_BREAK_FROM_KEYPOINT else cursor, next_point_down, positive=False):
                    cursor = self.action_keypoint_down(next_point_down)
                elif self.is_break_through(break_up):
                    cursor = self.action_break_through_up(break_up)
                else:
                    cursor = next_point_down+1 if COUNT_FOR_KEYPOINT_EQ_BREAKPOINT and next_point_down else next_point_down

        # Save last key_point
        ss = self.key_points.positive().indexes().tolist()
        self.save_data["kp_up"] = ss[-1] if ss else None
        ss = self.key_points.negative().indexes().tolist()
        self.save_data["kp_down"] = ss[-1] if ss else None
        self.save_data["state"] = self.state

        if self.save_point:
            self.break_through_points.working = self.break_through_points.array

        return self.break_through_points, self.key_points


class Incremental(object):
    '''
    Usage:
        dm = Incremental()
        # when one new data arrived:
        direction = dm.update(bar.price)
    '''
    def __init__(self, count=100) -> None:
        super().__init__()
        self.count = 100
        self.save_point = None
        self.offset = 0
        self.idx = 0
        self.base = -1
        self.data = np.zeros(self.count, dtype=float)

        self.breakpoint = set()
        self.keypoint = set()
        self.alternative = set()
        self.peakpoint = set()

    def extend(self, length=1):
        extra = np.zeros(length, dtype=float)
        self.data = np.concatenate((self.data, extra))

    def shrink(self, length):
        self.data = self.data[length:]

    def collect(self, data, collector):
        pickup = data.values().nonzero()[0] + self.base - self.offset
        pickup = set(pickup.tolist())
        collector.update(pickup)

    def update(self, data):
        '''
        Return:
            0:  Don't care
            <0: Sell
            >0: Buy
        '''
        ret = 0
        if self.idx >= self.count:
            if self.data.size < self.offset + self.count:
                # need extend
                self.extend()
            else:
                self.data[:-1] = self.data[1:]
            self.data[-1] = data
        else:
            self.data[self.idx] = data
        
        self.idx += 1
        if self.idx < self.count:
            return ret

        self.base += 1
        finder = ShapeFinder(self.data, save_point=self.save_point)
        alternative_points, peak_points, break_points, key_points = finder.search(self.base - self.offset)
        self.collect(alternative_points, self.alternative)
        self.collect(peak_points, self.peakpoint)
        self.collect(break_points, self.breakpoint)
        self.collect(key_points, self.keypoint)


        result = break_points.values().nonzero()[0]
        if result.size and int(result.max()) == self.data.size -1:
            ret = break_points.values()[self.data.size-1]

        self.save_point = finder.save_data
        need_offset = any([v<=self.offset for v in self.save_point.values() if isinstance(v, int)])
        if need_offset:
            self.offset += 1
        else:
            for k,v in self.save_point.items():
                if not isinstance(v, int):
                    continue
                self.save_point[k] = v-1-self.offset

            if  self.offset:
                # need shrink
                self.shrink(self.offset)
            self.offset = 0

        return ret
