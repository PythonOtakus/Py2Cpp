#ifndef PY2CPP_POSIX_PTHREAD_STUB_H
#define PY2CPP_POSIX_PTHREAD_STUB_H
typedef unsigned long pthread_t;
typedef struct pthread_attr_t { int _x; } pthread_attr_t;
typedef struct pthread_mutex_t { int _x; } pthread_mutex_t;
int pthread_create(pthread_t *thread, const pthread_attr_t *attr, void *(*start)(void *), void *arg);
int pthread_join(pthread_t thread, void **retval);
int pthread_detach(pthread_t thread);
int pthread_mutex_init(pthread_mutex_t *m, const void *attr);
int pthread_mutex_destroy(pthread_mutex_t *m);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
#endif
