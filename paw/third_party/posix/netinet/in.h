#ifndef PY2CPP_POSIX_NETINET_IN_STUB_H
#define PY2CPP_POSIX_NETINET_IN_STUB_H
typedef unsigned int in_addr_t;
struct in_addr { in_addr_t s_addr; };
struct sockaddr_in {
  unsigned short sin_family;
  unsigned short sin_port;
  struct in_addr sin_addr;
};
unsigned short htons(unsigned short hostshort);
unsigned int htonl(unsigned int hostlong);
unsigned short ntohs(unsigned short netshort);
unsigned int ntohl(unsigned int netlong);
#endif
