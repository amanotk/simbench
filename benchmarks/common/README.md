# Common Benchmark Includes

This directory stores shared headers used across benchmark task workspaces.

- `include/experimental/mdspan`: vendored mdspan headers (pinned to `mdspan-0.6.0`)

For C++ task workspaces, add this include path in build flags:

```make
-I../../../common/include
```

When using mdspan in C++17 workspaces, use:

```cpp
namespace stdex = std::experimental;
```
