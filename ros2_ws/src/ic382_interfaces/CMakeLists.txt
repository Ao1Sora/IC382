cmake_minimum_required(VERSION 3.8)
project(ic382_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(action_msgs REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/InspectDesk.action"
  "srv/CompleteInspection.srv"
  "msg/TaggingCommand.msg"
  "msg/PorterRequest.msg"
  "msg/DetectedObject.msg"
  "msg/DetectedObjectArray.msg"
  "msg/ObjectDetection.msg"
  "msg/ObjectDetectionArray.msg"
  "msg/AnomalyReport.msg"
  "msg/SafetyState.msg"
  "msg/InspectionContext.msg"
  DEPENDENCIES geometry_msgs builtin_interfaces std_msgs
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
