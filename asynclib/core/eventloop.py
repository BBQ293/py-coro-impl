from inspect import isgeneratorfunction
from enum import Enum, auto
import threading
from .eventQueue import eventQueue
from .model import Promise, AsyncapiWrapper, AsyncfunWrapper, Coroutine


class Loop:
    class LoopState(Enum):
        RUNNING = auto()
        STOPPED = auto()

    class __GeneratorExecutor:
        def __init__(self, coroutine: Coroutine):
            self.__coroutine = coroutine
            self.__next(None)

        def __next(self, currentValue):
            nextPromise: Promise = None
            try:
                nextPromise = self.__coroutine.coro.send(currentValue)
            except StopIteration as returnVal:
                self.__coroutine.emit('done', returnVal.value)
                return
            nextPromise.done(self.__next)

    __single = None

    @classmethod
    def getInstance(cls):
        if cls.__single is None:
            cls.__single = Loop()
        return cls.__single

    def __init__(self) -> None:
        self.__state:  Loop.LoopState = Loop.LoopState.STOPPED
        self.__stop = True

    def stop(self):
        if self.__state == Loop.LoopState.STOPPED:
            return
        self.__stop = True
        self.__state = Loop.LoopState.STOPPED

    def start(self):
        if self.__state == Loop.LoopState.RUNNING:
            return
        self.__stop = False
        self.__state = Loop.LoopState.RUNNING

        try:
            while True:
                cbk = eventQueue.getCallback()
                if isinstance(cbk, Coroutine):
                    self.__GeneratorExecutor(cbk)
                elif callable(cbk):
                    cbk()
                else:
                    raise TypeError(
                        'cbk is not callable, generator or generatable')
                if self.__stop:
                    return
        except KeyboardInterrupt:
            exit(0)


class LoopManager:
    __asyncTaskCount = 0
    __loopobj = Loop.getInstance()

    @classmethod
    def __loop(cls):
        threading.Thread(target=Loop.getInstance().start).start()

    @classmethod
    def __stopLoop(cls):
        cls.__loopobj.stop()

    @classmethod
    def __asyncStart(cls):
        cls.__asyncTaskCount += 1
        if cls.__asyncTaskCount == 1:
            cls.__loop()

    @classmethod
    def __asyncDone(cls):
        cls.__asyncTaskCount -= 1
        if cls.__asyncTaskCount == 0:
            cls.__stopLoop()

    @classmethod
    def __asyncapiStart(cls, asyncapiWrapped):
        cls.__asyncStart()

    @classmethod
    def __asyncapiDone(cls, asyncapiWrapped):
        cls.__asyncDone()

    @classmethod
    def __asyncfunStart(cls, asyncfunWrapped):
        cls.__asyncStart()

    @classmethod
    def __asyncfunDone(cls, asyncfunWrapped):
        cls.__asyncDone()

    # async api 的装饰器，用于维护所有异步任务的状态，管理事件循环
    # 只需要额外接收一个关键字参数 asyncTaskDone 即可实现一个对接到事件循环中的 async api
    @classmethod
    def asyncapi(cls, fun):
        return AsyncapiWrapper(fun).on('start', cls.__asyncapiStart).on('done', cls.__asyncapiDone)

    @classmethod
    def asyncfun(cls, coro):
        if not isgeneratorfunction(coro):
            raise TypeError('coro is not a generator function')

        return AsyncfunWrapper(coro).on('start', cls.__asyncfunStart).on('done', cls.__asyncfunDone)
