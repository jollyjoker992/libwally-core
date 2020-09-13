import os
import subprocess

# Structs with no definition in the public header files
OPAQUE_STRUCTS = [u'words']


def replace_text(filename, text, delims):
    lines = [line.rstrip() for line in open(filename)]
    start, end = lines.index(delims[0]), lines.index(delims[1])
    replaced = lines[:start + 1] + text + lines[end:]
    replaced = [l + u'\n' for l in replaced]
    open(filename, u'w').writelines([l for l in replaced])


class arg(object):
    def __init__(self, definition):
        if u'*' in definition:
            self.is_pointer = True
            self.is_pointer_pointer = u'**' in definition
            if self.is_pointer_pointer:
                self.type = definition.split(' **')[0] + '**'
            else:
                self.type = definition.split(' *')[0] + '*'
            self.name = definition[len(self.type) + 1:]
            self.is_struct = u'struct' in self.type
            if self.is_struct:
                self.struct_name = self.type.split(u' ')[-1].split(u'*')[0]
                self.is_opaque = self.struct_name in OPAQUE_STRUCTS
        else:
            self.is_pointer = False
            self.is_struct = False
            self.type, self.name = definition.split(' ')
        self.const = self.type.startswith(u'const ')


class func(object):
    def __init__(self, definition):
        # Strip return type and closing ')', extract name
        self.name, definition = definition[4:-1].split(u'(')
        # Parse arguments
        self.args = [arg(d) for d in definition.split(u', ')]


def gen_python_cffi(funcs):
    typemap = {
        u'int'           : u'c_int',
        u'size_t*'       : u'c_ulong_p',
        u'size_t'        : u'c_ulong',
        u'uint32_t*'     : u'c_uint_p',
        u'uint32_t'      : u'c_uint',
        u'uint64_t*'     : u'c_uint64_p',
        u'uint64_t'      : u'c_uint64',
        u'void**'        : u'POINTER(c_void_p)',
        u'void*'         : u'c_void_p',
        u'unsigned char*': u'c_void_p',
        u'char**'        : u'c_char_p_p',
        u'char*'         : u'c_char_p',
        }
    def map_arg(arg, n, num_args):
        argtype = arg.type[6:] if arg.const else arg.type # Strip const
        if argtype == u'uint64_t*' and n != num_args - 1:
            return u'POINTER(c_uint64)'
        if argtype in typemap:
            return typemap[argtype]
        if arg.is_struct:
            if arg.is_opaque:
                return typemap[u'void**' if arg.is_pointer_pointer else u'void*']
            text = f'POINTER({arg.struct_name})'
            if arg.is_pointer_pointer:
                text = f'POINTER({text})'
            return text
        assert False, f'ERROR: Unknown argument type "{argtype}"'

    cffi = []
    for func in funcs:
        num_args = len(func.args)
        mapped = u', '.join([map_arg(arg, i, num_args) for i, arg in enumerate(func.args)])
        cffi.append(f"    ('{func.name}', c_int, [{mapped}]),")

    cffi.sort()
    replace_text(u'src/test/util.py', cffi,
                 [u'    # BEGIN AUTOGENERATED', u'    # END AUTOGENERATED'])


if __name__ == "__main__":

     # Call sphinx to dump our definitions
    envs = {k:v for k,v in os.environ.items()}
    envs[u'WALLY_DOC_DUMP_FUNCS'] = u'1'
    cmd = ['sphinx-build', '-b', 'html', '-a', '-c', 'docs/source', 'docs/source', 'docs/build/html']
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=envs)

    # Process the lines into func objects for each function
    funcs = process.stdout.decode('utf-8').split(u'\n')
    funcs = [func(f) for f in funcs if f.startswith(u'int ')]

    gen_python_cffi(funcs)
