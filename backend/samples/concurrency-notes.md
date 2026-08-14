# 并发编程基础

## 线程基础

进程是资源分配单位，线程是调度单位。创建线程三种方式：
继承 Thread、实现 Runnable、实现 Callable（有返回值，配 Future）。
线程池 Executors/ThreadPoolExecutor：核心线程数、最大线程数、队列、
拒绝策略（Abort/丢弃最老/Discard/CallerRuns）。

## 线程安全三要素

原子性（synchronized/Lock/CAS）、可见性（volatile/锁，防止线程本地缓存）、
有序性（happens-before 规则，防止指令重排）。
volatile 保证可见性与有序性，不保证原子性（如 i++ 仍不安全）。

## 锁机制

- synchronized：JVM 内置锁，可重入；锁升级：偏向锁→轻量级锁→重量级锁；
- ReentrantLock：可中断、可公平、可超时、可绑定多条件（Condition）；
- CAS（Compare And Swap）：无锁更新，乐观并发；ABA 问题用版本号解决。

## 并发容器

ConcurrentHashMap（分段/桶锁 + CAS）、CopyOnWriteArrayList（写时复制，读多写少）、
BlockingQueue（生产者消费者，ArrayBlockingQueue 有界、LinkedBlockingQueue 可无界）。
ThreadLocal：线程私有变量，注意 remove 防止内存泄漏。
