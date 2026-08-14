# Spring 与 Spring Boot 基础

## IoC 与 DI

IoC（控制反转）：对象创建与依赖管理交给容器，而不是自己 new；
DI（依赖注入）是 IoC 的实现方式：构造器注入、Setter 注入、字段注入。
好处：解耦、便于测试（mock 依赖）、生命周期统一管理。

## AOP

面向切面：把日志、事务、鉴权等横切逻辑抽出来，动态织入业务方法。
底层：Spring 用 JDK 动态代理（接口）或 CGLIB（子类）。
常见注解：@Aspect、@Before、@AfterReturning、@Around（环绕通知最灵活）。

## Spring Boot 自动装配

@SpringBootApplication = @Configuration + @EnableAutoConfiguration + @ComponentScan。
自动装配原理：META-INF/spring.factories 里的 AutoConfiguration 按条件
（@ConditionalOnClass / @ConditionalOnMissingBean）生效，核心是
@EnableAutoConfiguration 通过 SpringFactoriesLoader 加载配置类。

## Bean 生命周期

实例化 → 属性填充 → Aware 回调 → BeanPostProcessor（before）→ init（@PostConstruct）
→ BeanPostProcessor（after）→ 使用 → @PreDestroy → 销毁。
常见作用域：singleton（默认，容器内单例）、prototype（每次获取新建）。
