/* AUTO: stub for ffi pyi generation on Windows hosts. Glue uses system <unistd.h>. */
#ifndef PY2CPP_POSIX_UNISTD_STUB_H
#define PY2CPP_POSIX_UNISTD_STUB_H
typedef int pid_t;
typedef int ssize_t;
unsigned int sleep(unsigned int seconds);
int usleep(unsigned int usec);
int close(int fd);
ssize_t read(int fd, void *buf, unsigned long count);
ssize_t write(int fd, const void *buf, unsigned long count);
int pipe(int pipefd[2]);
pid_t fork(void);
int execvp(const char *file, char *const argv[]);
int chdir(const char *path);
char *getcwd(char *buf, unsigned long size);
int access(const char *pathname, int mode);
int unlink(const char *pathname);
int rmdir(const char *pathname);
long sysconf(int name);
#endif
