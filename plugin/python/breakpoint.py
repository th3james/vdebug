import base64
import log

class Store:

    def __init__(self):
        self.breakpoints = {}
        self.api = None

    def link_api(self,api):
        self.api = api
        num_bps = len(self.breakpoints)
        if num_bps > 0:
            log.Log("Registering %i breakpoints with the debugger" % num_bps)
        for id, bp in self.breakpoints.iteritems():
            res = self.api.breakpoint_set(bp.get_cmd())
            bp.set_debugger_id(res.get_id())

    def unlink_api(self):
        self.api = None

    def add_breakpoint(self,breakpoint):
        log.Log("Adding " + str(breakpoint))
        self.breakpoints[str(breakpoint.get_id())] = breakpoint
        breakpoint.on_add()
        if self.api is not None:
            res = self.api.breakpoint_set(breakpoint.get_cmd())
            breakpoint.set_debugger_id(res.get_id())

    def remove_breakpoint(self,breakpoint):
        self.remove_breakpoint_by_id(\
                breakpoint.get_id())

    def remove_breakpoint_by_id(self,id):
        id = str(id)
        if id not in self.breakpoints:
            raise BreakpointError, "No breakpoint matching ID %s" % id
        log.Log("Removing breakpoint id %s" % id)
        if self.api is not None:
            dbg_id = self.breakpoints[id].get_debugger_id()
            if dbg_id is not None:
                self.api.breakpoint_remove(dbg_id)
        self.breakpoints[id].on_remove()
        del self.breakpoints[id]

    def clear_breakpoints(self):
        for id in self.breakpoints.keys():
            self.remove_breakpoint_by_id(id)
        self.breakpoints = {}

    def find_breakpoint(self,file,line):
        found = None
        for id, bp in self.breakpoints.iteritems():
            if bp.type == "line":
                if bp.get_file() == file and\
                        bp.get_line() == line:
                    found = bp.get_id()
                    break
        return found

    def get_sorted_list(self):
        keys = self.breakpoints.keys()
        keys.sort()
        return map(self.breakpoints.get,keys)

class BreakpointError(Exception):
    pass

class Breakpoint:
    """ Abstract factory for creating a breakpoint object.

    Use the class method parse to create a concrete subclass
    of a specific type.
    """
    type = None
    id = 11000
    dbg_id = None

    def __init__(self,ui):
        self.id = Breakpoint.id
        Breakpoint.id += 1 
        self.ui = ui

    def get_id(self):
        return self.id

    def set_debugger_id(self,dbg_id):
        self.dbg_id = dbg_id

    def get_debugger_id(self):
        return self.dbg_id

    def on_add(self):
        self.ui.register_breakpoint(self)

    def on_remove(self):
        self.ui.remove_breakpoint(self)

    @classmethod
    def parse(self,ui,args):
        if args is None:
            args = ""
        args = args.strip()
        if len(args) == 0:
            """ Line breakpoint """
            row = ui.get_current_row()
            file = ui.get_current_file()
            return LineBreakpoint(ui,file,row)
        else:
            arg_parts = args.split(' ')
            type = arg_parts.pop(0)
            type.lower()
            if type == 'conditional':
                row = ui.get_current_row()
                file = ui.get_current_file()
                if len(arg_parts) == 0:
                    raise BreakpointError, "Conditional breakpoints " +\
                            "require a condition to be specified"
                cond = " ".join(arg_parts)
                return ConditionalBreakpoint(ui,file,row,cond)
            elif type == 'exception':
                if len(arg_parts) == 0:
                    raise BreakpointError, "Exception breakpoints " +\
                            "require an exception name to be specified"
                return ExceptionBreakpoint(ui,arg_parts[0])
            elif type == 'return':
                if len(arg_parts) == 0:
                    raise BreakpointError, "Return breakpoints " +\
                            "require a function name to be specified"
                return ReturnBreakpoint(ui,arg_parts[0])
            elif type == 'call':
                if len(arg_parts) == 0:
                    raise BreakpointError, "Call breakpoints " +\
                            "require a function name to be specified"
                return CallBreakpoint(ui,arg_parts[0])
            else:
                raise BreakpointError, "Unknown breakpoint type, " +\
                        "please choose one of: conditional, exception,"+\
                        "call or return"

    def get_cmd(self):
        pass

    def __str__(self):
        return "%s breakpoint, id %i" %(self.type,self.id)

class LineBreakpoint(Breakpoint):
    type = "line"

    def __init__(self,ui,file,line):
        Breakpoint.__init__(self,ui)
        self.file = file
        self.line = line

    def get_line(self):
        return self.line

    def get_file(self):
        return self.file

    def get_cmd(self):
        cmd = "-t " + self.type
        cmd += " -f " + self.file.as_remote()
        cmd += " -n " + str(self.line)
        cmd += " -s enabled"
        
        return cmd

class TemporaryLineBreakpoint(LineBreakpoint):
    def on_add(self):
        pass

    def on_remove(self):
        pass

    def get_cmd(self):
        cmd = LineBreakpoint.get_cmd(self)
        return cmd + " -r 1"

class ConditionalBreakpoint(LineBreakpoint):
    type = "conditional"

    def __init__(self,ui,file,line,condition):
        LineBreakpoint.__init__(self,ui,file,line)
        self.condition = condition

    def get_cmd(self):
        cmd = LineBreakpoint.get_cmd(self)
        cmd += " -- " + base64.encodestring(self.condition)
        return cmd

class ExceptionBreakpoint(Breakpoint):
    type = "exception"

    def __init__(self,ui,exception):
        Breakpoint.__init__(self,ui)
        self.exception = exception

    def get_cmd(self):
        cmd = "-t " + self.type
        cmd += " -x " + self.exception
        cmd += " -s enabled"
        return cmd

class CallBreakpoint(Breakpoint):
    type = "call"

    def __init__(self,ui,function):
        Breakpoint.__init__(self,ui)
        self.function = function

    def get_cmd(self):
        cmd = "-t " + self.type
        cmd += " -m " + self.function
        cmd += " -s enabled"
        return cmd

class ReturnBreakpoint(CallBreakpoint):
    type = "return"
