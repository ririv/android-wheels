# Android API 24 起支持 DT_RUNPATH；让 CMake 保留上游声明的 $ORIGIN。
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Android")
  message(FATAL_ERROR "This configuration requires an Android target")
endif()
set(CMAKE_SHARED_LIBRARY_RUNTIME_C_FLAG "-Wl,-rpath,")
set(CMAKE_SHARED_LIBRARY_RUNTIME_CXX_FLAG "-Wl,-rpath,")
