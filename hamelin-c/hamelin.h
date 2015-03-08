#ifndef HAMELIN_H
#define HAMELIN_H

#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/select.h>
//#include <sys/socket.h>
//http://www.csd.uoc.gr/~hy556/material/tutorials/cs556-3rd-tutorial.pdf
#include <sched.h>

// Thread-safe message queue.

typedef enum {
    H_LOCKED,
    H_UNLOCKED
} H_lock_status_t;

typedef struct H_queue_link {
    struct H_queue_link* next;
    char*         datum;
} H_queue_link;

typedef struct H_message_queue {
    H_lock_status_t lock;
    H_queue_link*   enqueue;
    H_queue_link*   dequeue;
} H_message_queue;

int H_queue_init(H_message_queue* q);

int H_acquire_queue_lock(H_message_queue* q);
int H_release_queue_lock(H_message_queue* q);

char* H_dequeue(H_message_queue* q);
int   H_isempty(H_message_queue* q);
int   H_enqueue(H_message_queue* q, char* datum);

// Subprocess interface

typedef struct H_server {
    H_message_queue* read_queue;
    H_message_queue* write_queue;
    char*            command;
    char**           args;
    char**           env;
} H_server;

int H_launch_server(H_server* server);

#endif
