# Java 基础面试笔记

## JVM 内存模型

JVM 运行时数据区：堆（对象实例，GC 主战场）、方法区/元空间（类元数据）、
虚拟机栈（方法帧，局部变量）、本地方法栈、程序计数器。
栈存引用、堆存对象，值类型直接存在栈上。

## 垃圾回收

对象可达性分析（GC Roots 出发）判定存活；分代收集：
新生代（Eden + 两个 Survivor，复制算法，Minor GC）→ 老年代（标记-整理/标记-清除，Major/Full GC）。
常用收集器：CMS（低停顿）、G1（分区 + 可预测停顿，JDK9+ 默认）。

## 集合框架

- ArrayList：动态数组，随机访问 O(1)，扩容 1.5 倍；
- LinkedList：双向链表，插入删除 O(1)（需先定位）；
- HashMap：数组+链表+红黑树，扰动函数降低哈希冲突，JDK8 链表>8 转红黑树；
- ConcurrentHashMap：CAS + synchronized 锁桶头，读无锁。

## String 相关

String 不可变（final char[]），字符串常量池；StringBuilder 可变非线程安全、
StringBuffer 可变线程安全（方法加锁）。
字符串拼接在循环里用 StringBuilder，避免产生大量中间对象。
