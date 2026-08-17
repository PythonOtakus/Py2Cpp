#ifndef PY2CPP_POSIX_SYS_SOCKET_STUB_H
#define PY2CPP_POSIX_SYS_SOCKET_STUB_H
typedef unsigned long long socklen_t;
int socket(int domain, int type, int protocol);
int bind(int sockfd, const void *addr, socklen_t addrlen);
int listen(int sockfd, int backlog);
int accept(int sockfd, void *addr, socklen_t *addrlen);
int connect(int sockfd, const void *addr, socklen_t addrlen);
int setsockopt(int sockfd, int level, int optname, const void *optval, socklen_t optlen);
int getsockopt(int sockfd, int level, int optname, void *optval, socklen_t *optlen);
#endif
