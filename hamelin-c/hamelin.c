#include "hamelin.h"

int H_queue_init(H_message_queue* q) {
    q->lock = H_UNLOCKED;
    q->enqueue = NULL;
    q->dequeue = NULL;
    return 0;
}

int H_acquire_queue_lock(H_message_queue* q) {
    while (q->lock == H_LOCKED) {
        if (sched_yield()) {
            return 1;
        }
    }
    q->lock = H_LOCKED;
    return 0;
}

int H_release_queue_lock(H_message_queue* q) {
    q->lock = H_UNLOCKED;
    return 0;
}

char* H_dequeue(H_message_queue* q) {
    H_queue_link* temp = q->dequeue;
    char* ret = temp->datum;
    if (q->dequeue == q->enqueue) {
        q->dequeue = NULL;
        q->enqueue = NULL;
    } else {
        q->dequeue = temp->next;
    }
    free(temp);
    return ret;
}

int H_enqueue(H_message_queue* q, char* datum) {
    H_queue_link* l = (H_queue_link*)malloc(sizeof(H_queue_link));
    if (l == NULL) {
        return 1;
    }
    l->next = NULL;
    l->datum = datum;

    if (H_isempty(q)) {
        q->enqueue = l;
        q->dequeue = l;
        return 0;
    } else {
        q->enqueue->next = l;
        q->enqueue = q->enqueue->next;
        return 0;
    }
}

int H_isempty(H_message_queue* q) {
    if (q->enqueue == NULL && q->dequeue == NULL) {
        return 1;
    } else {
        return 0;
    }
}

void* _H_subprocess(void* info) {
    H_server* server = (H_server*) info;
    // Two pipes for bidirectional communication
    int parentToChild[2];
    int childToParent[2];

    if (pipe(parentToChild) || pipe(childToParent)) {
        printf("Couldn't pipe.\n");
    }

    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "Error: couldn't fork.\n");
        exit(1);
    } else {
        if (pid == 0) {
            // I am a child.

            // Close unused file descriptors (i.e. the ends of the pipes that
            // we don't actually use). If we don't do this, then the process
            // refuses to die.
            close(parentToChild[1]);
            close(childToParent[0]);

            // Copy the files as standard I/O.
            // What it actually does is rename the standard I/O descriptors as
            // our IPC pipe. Whatever.
            dup2(parentToChild[0], STDIN_FILENO);
            dup2(childToParent[1], STDOUT_FILENO);

            // At some point, make sure this is doing the right thing.
            // dup2(childToParent[1], STDERR_FILENO);

            // Execute the process.
            /*
            execve(
                "/usr/bin/grep",
                (char*[]) {
                    "/usr/bin/grep",
                    "--line-buffered",
                    "cow",
                    (char*)NULL
                },
                (char*[]){
                    "H-VERSION=C-EXPERIMENTAL",
                    (char*)NULL
                }
            );*/
            execve(server->command, server->args, server->env);
        } else {
            // I am the parent.
            // As above^^, let's close the unused ends of the pipes.
            close(parentToChild[0]);
            close(childToParent[1]);
            
            FILE* f = fdopen(parentToChild[1], "w");
            FILE* g = fdopen(childToParent[0], "r");
            char line[1024];

            int status;
            pid_t result;

            fd_set fdset_r;
            fd_set fdset_w;
            struct timeval timeout;
            int ret;
            while ((result = waitpid(pid, &status, WNOHANG)) == 0) {
                FD_ZERO(&fdset_r);
                FD_ZERO(&fdset_w);
                FD_SET(childToParent[0], &fdset_r);
                FD_SET(STDIN_FILENO, &fdset_r);
                timeout.tv_sec = 0;
                timeout.tv_usec = 1;
                select(childToParent[0]+1, &fdset_r, NULL, NULL, &timeout);

                if (FD_ISSET(STDIN_FILENO, &fdset_r)) {
                    // TODO: Detect EOF properly and give up when you get it.
                    if (fgets(line, sizeof(line), stdin) == NULL) {
                        fclose(stdin);
                        fclose(f);
                    } else {
                        fprintf(f, "%s", line);
                        fflush(f);
                    }
                }

                if (FD_ISSET(childToParent[0], &fdset_r)) {
                    if (fgets(line, sizeof(line), g) == NULL) {
                        fclose(g);
                    } else {
                        printf("%s", line);
                        fflush(stdout);
                    }
                }
            }
            if (result == -1) {
                printf("Error with waitpid.");
            } else {
                printf("Subproc exited with status %d.\n", status);
            }
        }
    }
    return 0;
}

int H_launch_server(H_server* server) {
    pthread_t thread;
    // https://computing.llnl.gov/tutorials/pthreads/
    pthread_create(&thread, NULL, _H_subprocess, server);
    // A detached thread will free resources when it exits.
    pthread_detach(thread);
    return 0;
}

int main() {
    H_server server;
    H_message_queue read_queue;
    H_message_queue write_queue;

    server.read_queue = &read_queue;
    server.write_queue = &write_queue;
    H_queue_init(server.read_queue);
    H_queue_init(server.write_queue);

    server.command = "/usr/bin/grep";
    server.args = (char*[]){"/usr/bin/grep", "--line-buffered", "cow", (char*)NULL};
    server.env  = (char*[]){"H-VERSION=C-EXPERIMENTAL", (char*)NULL};
    H_launch_server(&server);
    
    while (1) {
        sleep(0);
    }
}
