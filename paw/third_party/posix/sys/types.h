#ifndef PY2CPP_POSIX_SYS_TYPES_STUB_H
#define PY2CPP_POSIX_SYS_TYPES_STUB_H
/* 避免与 MSVC/clang 内建 size_t 冲突；仅暴露 POSIX 专用别名 */
typedef int pid_t;
typedef long off_t;
typedef int ssize_t;
typedef unsigned int mode_t;
typedef unsigned int uid_t;
typedef unsigned int gid_t;
/* 供 c_ffi_pyi 收集至少一个函数符号（仅 typedef 时 funcs=0） */
void py2cpp_posix_sys_types_anchor(void);
#endif
