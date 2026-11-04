#include <algorithm>
#include <cmath>
#include "nav2_core/exceptions.hpp"
#include "nav2_regulated_pure_pursuit_controller/regulated_pure_pursuit_controller.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "tf2/utils.h"

namespace ic382_planners
{
class StagedGoalController : public nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController
{
  geometry_msgs::msg::PoseStamped goal_;
  bool have_goal_{false};
  bool aligning_{false};
  double xy_tolerance_{0.1};
  double yaw_tolerance_{0.15};

  geometry_msgs::msg::TwistStamped rotate(
    const geometry_msgs::msg::PoseStamped & pose, double error)
  {
    geometry_msgs::msg::TwistStamped command;
    command.header = pose.header;
    if (std::abs(error) < 0.9 * yaw_tolerance_) {return command;}
    // Operator policy: pure in-place turns bypass predicted footprint collision.
    // Translation still goes through the base controller's collision prediction.
    command.twist.angular.z = std::copysign(rotate_to_heading_angular_vel_, error);
    return command;
  }

public:
  void setPlan(const nav_msgs::msg::Path & path) override
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (path.poses.empty()) {throw nav2_core::PlannerException("Empty controller path");}
    goal_ = path.poses.back();
    if (goal_.header.frame_id.empty()) {goal_.header.frame_id = path.header.frame_id;}
    have_goal_ = true;
    aligning_ = false;
    nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController::setPlan(path);
  }

  geometry_msgs::msg::TwistStamped computeVelocityCommands(
    const geometry_msgs::msg::PoseStamped & pose, const geometry_msgs::msg::Twist & speed,
    nav2_core::GoalChecker * checker) override
  {
    std::unique_lock<std::mutex> lock(mutex_);
    if (!have_goal_) {throw nav2_core::PlannerException("No controller goal");}
    geometry_msgs::msg::Pose tolerance;
    geometry_msgs::msg::Twist velocity_tolerance;
    if (checker->getTolerances(tolerance, velocity_tolerance)) {
      xy_tolerance_ = tolerance.position.x;
      yaw_tolerance_ = std::abs(tf2::getYaw(tolerance.orientation));
    }
    geometry_msgs::msg::PoseStamped current;
    if (!transformPose(goal_.header.frame_id, pose, current)) {
      throw nav2_core::PlannerException("Cannot transform pose into goal frame");
    }
    const double distance = std::hypot(goal_.pose.position.x - current.pose.position.x,
      goal_.pose.position.y - current.pose.position.y);
    if (!aligning_ && distance <= xy_tolerance_) {
      aligning_ = true;
      RCLCPP_INFO(logger_, "Position reached: locking translation, aligning exact goal heading");
    }
    if (aligning_) {
      const double difference = tf2::getYaw(goal_.pose.orientation) - tf2::getYaw(current.pose.orientation);
      return rotate(pose, std::atan2(std::sin(difference), std::cos(difference)));
    }
    // Handle path alignment explicitly; base RPP's carrot-distance test must not
    // enter goal-yaw alignment before the actual target position is reached.
    auto local_path = transformGlobalPlan(pose);
    auto carrot = getLookAheadPoint(getLookAheadDistance(speed), local_path);
    const double heading = std::atan2(carrot.pose.position.y, carrot.pose.position.x);
    if (std::abs(heading) > rotate_to_heading_min_angle_) {return rotate(pose, heading);}
    lock.unlock();
    return nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController::computeVelocityCommands(
      pose, speed, checker);
  }
};
}  // namespace ic382_planners
PLUGINLIB_EXPORT_CLASS(ic382_planners::StagedGoalController, nav2_core::Controller)
