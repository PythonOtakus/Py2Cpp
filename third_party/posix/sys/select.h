#ifndef PY2CPP_POSIX_SYS_SELECT_STUB_H
#define PY2CPP_POSIX_SYS_SELECT_STUB_H
typedef struct fd_set { unsigned long fds_bits[32]; } fd_set;
struct timeval { long tv_sec; long tv_usec; };
int select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds, struct timeval *timeout);
void FD_ZERO(fd_set *set);
void FD_SET(int fd, fd_set *set);
int FD_ISSET(int fd, fd_set *set);
#endif
