import gc
import uasyncio as asyncio
from sys import platform
from pysmartnode import config

if config.DEBUG:
    def __printRAM(start, info=""):
        print(info, "Mem free", gc.mem_free(), "diff:", gc.mem_free() - start)
else:
    __printRAM = lambda *_: None


def _checkArgs(d, _log):
    required = ("package", "component")
    for r in required:
        if r not in d:
            _log.error("Missing required value {!r} in component".format(r))
            return False
    return True


def _getKwargs(kwargs):
    if type(kwargs) != dict:
        return {}
    COMPONENTS = config.COMPONENTS
    for key in kwargs:
        arg = kwargs[key]
        if type(arg) == str:
            if arg in COMPONENTS:
                kwargs[key] = COMPONENTS[arg]
    return kwargs


def _getArgs(args):
    if type(args) != list:
        return []
    COMPONENTS = config.COMPONENTS
    for i in range(0, len(args)):
        if type(args[i]) == str:
            if args[i] in COMPONENTS:
                args[i] = COMPONENTS[args[i]]
    return args


def _checkPackage(data):
    if data["package"].startswith("."):
        data["package"] = "pysmartnode.components" + data["package"]


async def registerComponentsAsync(data, _log):
    for component in data["_order"]:
        tmp = {"_order": [component]}
        tmp[component] = data[component]
        await _registerComponents(tmp, _log)
        del tmp
        gc.collect()
        await asyncio.sleep_ms(750 if platform == "esp8266" else 200)
        gc.collect()


async def _registerComponents(data, _log):
    gc.collect()
    mem_start = gc.mem_free()
    __printRAM(mem_start)
    res = False
    # res: Result of registering a component
    # makes only sense if only a single component is being registered at a time
    order = data["_order"] if "_order" in data else list(data.keys())
    COMPONENTS = config.COMPONENTS
    loop = asyncio.get_event_loop()
    for i in range(0, len(order)):
        if order[i] not in data:
            await _log.asyncLog("error", "component {!r} of order is not in component dict".format(data["_order"][i]))
        else:
            version = None
            componentname = order[i]
            if componentname in COMPONENTS:
                await _log.asyncLog("critical", "Component {!r} already added".format(componentname))
                # False will be returned as res = False if only one component is added
            else:
                component = data[componentname]
                if _checkArgs(data[componentname], _log):
                    _checkPackage(data[componentname])
                    try:
                        tmp = __import__(component["package"], globals(),
                                         locals(), [component["component"]], 0)
                    except Exception as e:
                        await _log.asyncLog("critical", "Error importing package {!s}, error: {!s}".format(
                            component["package"], e))
                        tmp = None
                    gc.collect()
                    err = False
                    if tmp is not None:
                        if hasattr(tmp, "__version__"):
                            version = getattr(tmp, "__version__")
                        if hasattr(tmp, component["component"]):
                            kwargs = _getKwargs(
                                component["constructor_args"]) if "constructor_args" in component and type(
                                component["constructor_args"]) == dict else {}
                            args = _getArgs(
                                component["constructor_args"]) if "constructor_args" in component and type(
                                component["constructor_args"]) == list else []
                            try:
                                obj = getattr(tmp, component["component"])
                                if str(type(obj)) == "<class 'generator'>":
                                    obj = await obj(*args, **kwargs)
                                else:
                                    obj = obj(*args, **kwargs)
                            except Exception as e:
                                await _log.asyncLog("error",
                                                    "Error during creation of object {!r}, {!r}, version {!s}: {!s}".format(
                                                        component["component"], componentname, version, e))
                                obj = None
                                err = True
                            if obj is not None:
                                err = False
                                if "init_function" in component and component["init_function"] is not None:
                                    kwargs = _getKwargs(component["init_args"]) if "init_args" in component and type(
                                        component["init_args"]) == dict else {}
                                    args = _getArgs(component["init_args"]) if "init_args" in component and type(
                                        component["init_args"]) == list else []
                                    if "init_function" in component and hasattr(obj, component["init_function"]):
                                        init = getattr(obj, component["init_function"])
                                        if type(init) == type(registerComponentsAsync):
                                            from pysmartnode.utils.wrappers.callAsyncSafe import \
                                                callAsyncSafe as _callAsyncSafe
                                            await _callAsyncSafe(init, component["init_function"], args, kwargs)
                                        else:
                                            try:
                                                tmp_init = init(*args, **kwargs)
                                                if type(tmp_init) == type(registerComponentsAsync):
                                                    await tmp_init
                                            except Exception as e:
                                                await _log.asyncLog("critical",
                                                                    "Error calling init function {!r}, {!r}, version {!s}: {!e}".format(
                                                                        component["init_function"], componentname,
                                                                        version, e))
                                                err = True
                                    else:
                                        await _log.asyncLog("critical",
                                                            "init function {!r} does not exist for object {!r}, version {!s}".format(
                                                                component["init_function"], componentname, version))
                                        err = True
                                if err is False and "call_function_regularly" in component and component[
                                    "call_function_regularly"] is not None:
                                    if hasattr(obj, component["call_function_regularly"]) is False:
                                        await _log.asyncLog("critical", "obj has no function {!r}".format(
                                            component["call_function_regularly"]))
                                    else:
                                        func = getattr(obj, component["call_function_regularly"])
                                        from pysmartnode.utils.wrappers.callRegular import callRegular
                                        loop.create_task(callRegular(func, component[
                                            "call_interval"] if "call_interval" in component else None))
                                if err is False:
                                    COMPONENTS[componentname] = obj
                                    await _log.asyncLog("info", "Added component {!r}, version {!s}".format(
                                        componentname, version))
                                    res = True
                            elif err is False:
                                await _log.asyncLog("info", "Added component {!r}, version {!s} as service".format(
                                    componentname, version))  # probably function, not class
                                res = True
                            else:
                                res = False
                        else:
                            await _log.asyncLog("critical",
                                                "error during import of module {!s}".format(component["component"]))
                            res = False
            gc.collect()
            __printRAM(mem_start)
    return res
