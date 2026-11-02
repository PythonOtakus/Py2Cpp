#ifndef PY2CPP_POSIX_DIRENT_STUB_H
#define PY2CPP_POSIX_DIRENT_STUB_H
typedef struct DIR DIR;
struct dirent { char d_name[256]; };
DIR *opendir(const char *name);
struct dirent *readdir(DIR *dirp);
int closedir(DIR *dirp);
#endif
