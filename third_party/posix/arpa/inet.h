#ifndef PY2CPP_POSIX_ARPA_INET_STUB_H
#define PY2CPP_POSIX_ARPA_INET_STUB_H
unsigned int inet_addr(const char *cp);
char *inet_ntoa(struct in_addr in);
int inet_pton(int af, const char *src, void *dst);
const char *inet_ntop(int af, const void *src, char *dst, unsigned long size);
struct in_addr { unsigned int s_addr; };
#endif
