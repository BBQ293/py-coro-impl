from typing import Any, Callable, List
from .eventQueue import eventQueue


class Emitter:
    def __init__(self) -> None:
        self.__eventMap: dict[str, list[Callable]] = {}

    def on(self, event: str, cbk: Callable):
        if event in self.__eventMap:
            self.__eventMap[event].append(cbk)
        else:
            self.__eventMap[event] = [cbk]
        return self

    def emit(self, event: str, *args, **kwds):
        if event in self.__eventMap:
            for cbk in self.__eventMap[event]:
                cbk(*args, **kwds)
        return self


class Promise:

    def __init__(self, task=lambda resolve: resolve()):
        self.__callbacks: List[Callable[[Any], Any]] = []
        self.__value: Any = None
        self.__state: str = 'pending'
        task(self.resolve)

    def resolve(self, value: Any = None):
        if self.__state == 'resolved':
            return
        self.__value = value
        self.__state = 'resolved'
        for cbk in self.__callbacks:
            cbk(self.__value)
        return self

    def done(self, cbk: Callable[[Any], Any]):
        if self.__state == 'resolved':
            cbk(self.__value)
        self.__callbacks.append(cbk)
        return self

    def __iter__(self):
        yield self
        return self.__value


# 底层接口, 用户开发者的协程将被该类包装, 执行结束后被执行器触发 done 事件回调
class Coroutine(Emitter):
    def __init__(self, coro) -> None:
        super().__init__()
        self.coro = coro


# async api 抽象层, 位于事件循环和 async api 之间
class AsyncapiWrapper(Emitter):
    def __init__(self, asyncapi) -> None:
        super().__init__()
        self.__asyncapi = asyncapi
        self.result = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.emit('start', self)
        self.__asyncapi(
            *args,
            **kwds,
            asyncDone=self.__done
        )

    def __done(self, result):
        self.result = result
        self.emit('done', self)


# 这是一个可执行的开发者用户的协程抽象层, 位于事件循环和协程包装(Coroutine)之间
class AsyncfunWrapper(Emitter):
    def __init__(self, asyncfun) -> None:
        super().__init__()
        self.__asyncfun = asyncfun
        self.result = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.emit('start', self)
        coro = Coroutine(self.__asyncfun(*args, **kwds))
        eventQueue.pushCallback(coro)
        return Promise(
            lambda resolve:
            (coro.on('done', lambda result: resolve(result)),
             coro.on('done', self.__done))
        )

    def __done(self, result):
        self.result = result
        self.emit('done', self)
