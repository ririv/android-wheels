# 从构建器的显式目标前缀发现原生依赖，兼容新旧构建器的不同目录。
if(NOT IS_DIRECTORY "$ENV{NATIVE_PREFIX}/lib")
  message(FATAL_ERROR "NATIVE_PREFIX must contain the prepared Android SDK libraries")
endif()
list(PREPEND CMAKE_PREFIX_PATH "$ENV{NATIVE_PREFIX}")
list(PREPEND CMAKE_FIND_ROOT_PATH "$ENV{NATIVE_PREFIX}")
