#ifndef PY2CPP_POSIX_SYS_WAIT_STUB_H
#define PY2CPP_POSIX_SYS_WAIT_STUB_H
typedef int pid_t;
pid_t waitpid(pid_t pid, int *status, int options);
pid_t wait(int *status);
#endif
