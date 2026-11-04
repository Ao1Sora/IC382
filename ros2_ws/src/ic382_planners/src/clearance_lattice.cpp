#include <cmath>
#include <stdexcept>
#include <queue>
#include <vector>
#include <limits>
#include <functional>
#include "nav2_core/exceptions.hpp"
#include "nav2_smac_planner/smac_planner_lattice.hpp"
#include "nav2_costmap_2d/footprint.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "nav2_costmap_2d/footprint_collision_checker.hpp"
#include "tf2/utils.h"

namespace ic382_planners
{
// Add only sub-lethal route preference costs while planning. Collision checks
// always use the measured body; tight passages stay traversable.
class ClearanceLattice : public nav2_smac_planner::SmacPlannerLattice
{
  nav2_costmap_2d::Footprint planning_body_;
  double preferred_clearance_{0.1};
  double body_radius_{0.0};

  void preferClearance(const std::vector<unsigned char> & original)
  {
    const auto width=_costmap->getSizeInCellsX(), height=_costmap->getSizeInCellsY();
    const double resolution=_costmap->getResolution();
    const double range=body_radius_+preferred_clearance_;
    if (preferred_clearance_<=0.0 || range<=0.0) {return;}
    std::vector<float> distance(original.size(),std::numeric_limits<float>::infinity());
    using Item=std::pair<float,size_t>;
    std::priority_queue<Item,std::vector<Item>,std::greater<Item>> frontier;
    for (size_t i=0;i<original.size();++i) {
      if (original[i]>=nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE) {
        distance[i]=0.0;frontier.emplace(0.0,i);
      }
    }
    while (!frontier.empty()) {
      const auto current=frontier.top();frontier.pop();
      const float d=current.first;const size_t index=current.second;
      if (d>distance[index]+1e-6 || d>range) {continue;}
      const int x=index%width,y=index/width;
      for (int dy=-1;dy<=1;++dy) {for (int dx=-1;dx<=1;++dx) {
        if ((dx==0 && dy==0) || x+dx<0 || y+dy<0 ||
          x+dx>=static_cast<int>(width) || y+dy>=static_cast<int>(height)) {continue;}
        const size_t next=(y+dy)*width+x+dx;
        const float candidate=d+resolution*((dx!=0 && dy!=0)?std::sqrt(2.0):1.0);
        if (candidate<=range && candidate+1e-6<distance[next]) {
          distance[next]=candidate;frontier.emplace(candidate,next);
        }
      }}
    }
    auto cells=_costmap->getCharMap();
    for (size_t i=0;i<original.size();++i) {
      if (original[i]>=nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE || distance[i]>=range) {continue;}
      // A finite smooth penalty favours the largest minimum wall distance. In
      // a narrow corridor that favours the middle without making its cells lethal.
      const double proximity=1.0-distance[i]/range;
      const unsigned char preference=static_cast<unsigned char>(220.0*proximity*proximity);
      cells[i]=std::max(original[i],preference);
    }
  }


  bool clearPose(double x, double y, double yaw)
  {
    nav2_costmap_2d::Footprint polygon;
    nav2_costmap_2d::transformFootprint(x, y, yaw, planning_body_, polygon);
    double min_x=polygon.front().x, max_x=min_x, min_y=polygon.front().y, max_y=min_y;
    for (const auto & p : polygon) {
      min_x=std::min(min_x,p.x);max_x=std::max(max_x,p.x);
      min_y=std::min(min_y,p.y);max_y=std::max(max_y,p.y);
    }
    unsigned int left, bottom, right, top;
    if (!_costmap->worldToMap(min_x,min_y,left,bottom) ||
      !_costmap->worldToMap(max_x,max_y,right,top)) {return false;}
    const double half=_costmap->getResolution()/2;
    for (unsigned int my=bottom;my<=top;++my) {
      for (unsigned int mx=left;mx<=right;++mx) {
        if (_costmap->getCost(mx,my)<nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE) {continue;}
        double cx,cy;_costmap->mapToWorld(mx,my,cx,cy);
        bool separated=false;
        // Filled polygon-vs-cell intersection, including obstacles wholly inside
        // the measured body that an outline-only footprint check can miss.
        for (size_t axis=0;axis<polygon.size()+2;++axis) {
          double nx=1.0,ny=0.0;
          if (axis==1) {nx=0.0;ny=1.0;}
          if (axis>=2) {
            const auto & a=polygon[axis-2];const auto & b=polygon[(axis-1)%polygon.size()];
            nx=b.y-a.y;ny=a.x-b.x;
          }
          double lo=polygon.front().x*nx+polygon.front().y*ny, hi=lo;
          for (const auto & p : polygon) {const double v=p.x*nx+p.y*ny;lo=std::min(lo,v);hi=std::max(hi,v);}
          const double centre=cx*nx+cy*ny, extent=half*(std::abs(nx)+std::abs(ny));
          if (hi<centre-extent-1e-9 || centre+extent<lo-1e-9) {separated=true;break;}
        }
        if (!separated) {return false;}
      }
    }
    return true;
  }
public:
  void configure(const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
    std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap) override
  {
    auto node = parent.lock();
    if (!node) {throw std::runtime_error("Planner parent expired");}
    const auto key = name + ".planning_clearance";
    if (!node->has_parameter(key)) {node->declare_parameter(key, 0.10);}
    const double clearance = node->get_parameter(key).as_double();
    if (!std::isfinite(clearance) || clearance < 0.0 || clearance > 0.1) {
      throw std::invalid_argument("Recovery planning clearance must be 0..0.1 m");
    }
    preferred_clearance_=clearance;
    planning_body_=costmap->getUnpaddedRobotFootprint();
    body_radius_=0.0;
    for (const auto & p : planning_body_) {body_radius_=std::max(body_radius_,std::hypot(p.x,p.y));}
    // Configure the lattice with the real body, never a padded preference body.
    nav2_smac_planner::SmacPlannerLattice::configure(parent,name,tf,costmap);
    RCLCPP_INFO(node->get_logger(), "Soft route preference %.3f m; collision body unchanged", clearance);
  }

  nav_msgs::msg::Path validatePath(nav_msgs::msg::Path path,
    const geometry_msgs::msg::PoseStamped & start, const geometry_msgs::msg::PoseStamped & goal)
  {
    if (path.poses.empty()) {return path;}
    // The lattice has 16 heading bins. Preserve the requested exact goal pose,
    // including its final yaw, instead of aligning to a quantized bin forever.
    path.poses.push_back(goal);
    std::unique_lock<nav2_costmap_2d::Costmap2D::mutex_t> lock(*_costmap->getMutex());
    auto previous = start;
    for (const auto & next : path.poses) {
      const double a = tf2::getYaw(previous.pose.orientation);
      const double delta = std::atan2(std::sin(tf2::getYaw(next.pose.orientation) - a),
        std::cos(tf2::getYaw(next.pose.orientation) - a));
      const double dx = next.pose.position.x - previous.pose.position.x;
      const double dy = next.pose.position.y - previous.pose.position.y;
      const int steps = std::max(1, static_cast<int>(std::ceil(std::max(
        std::hypot(dx, dy) / 0.02, std::abs(delta) / 0.025))));
      for (int i = 0; i <= steps; ++i) {
        const double ratio = static_cast<double>(i) / steps;
        if (!clearPose(
          previous.pose.position.x + ratio * dx, previous.pose.position.y + ratio * dy,
          a + ratio * delta)) {
          throw nav2_core::PlannerException("Measured body intersects an obstacle along path or final rotation");
        }
      }
      previous = next;
    }
    return path;
  }

  void searchBody(const nav2_costmap_2d::Footprint & body)
  {
    planning_body_=body;
    // Rebuild the orientation cache when switching between preferred and actual
    // bodies; Humble's setFootprint appends cached orientations on repeated calls.
    _collision_checker=nav2_smac_planner::GridCollisionChecker(_costmap,72u);
    _collision_checker.setFootprint(body,false,-1.0);
  }

  nav_msgs::msg::Path createPlan(const geometry_msgs::msg::PoseStamped & start,
    const geometry_msgs::msg::PoseStamped & goal) override
  {
    std::unique_lock<nav2_costmap_2d::Costmap2D::mutex_t> map_lock(*_costmap->getMutex());
    struct RestoreCosts {
      nav2_costmap_2d::Costmap2D * map;
      std::vector<unsigned char> original;
      explicit RestoreCosts(nav2_costmap_2d::Costmap2D * value):map(value),
        original(value->getCharMap(),value->getCharMap()+value->getSizeInCellsX()*value->getSizeInCellsY()) {}
      void restore() {std::copy(original.begin(),original.end(),map->getCharMap());}
      ~RestoreCosts() {restore();}
    } costs(_costmap);
    const auto measured=planning_body_;
    try {
      if (preferred_clearance_>0.0) {
        auto preferred=measured;
        nav2_costmap_2d::padFootprint(preferred,preferred_clearance_);
        searchBody(preferred);
        // A nearby start/goal must not be rejected just for missing the preference.
        if (clearPose(start.pose.position.x,start.pose.position.y,tf2::getYaw(start.pose.orientation)) &&
          clearPose(goal.pose.position.x,goal.pose.position.y,tf2::getYaw(goal.pose.orientation))) {
          try {
            auto path=nav2_smac_planner::SmacPlannerLattice::createPlan(start,goal);
            if (!path.poses.empty()) {
              path=validatePath(path,start,goal);
              searchBody(measured);
              RCLCPP_INFO(_logger,"Using route with preferred 10 cm obstacle clearance");
              return path;
            }
          } catch (const nav2_core::PlannerException &) {
            // Failure of a preference is never a physical collision failure.
          }
        }
      }
      searchBody(measured);
      RCLCPP_INFO(_logger,"Preference unavailable: planning central route using measured collision body");
      preferClearance(costs.original);
      auto path=nav2_smac_planner::SmacPlannerLattice::createPlan(start,goal);
      costs.restore();
      return validatePath(path,start,goal);
    } catch (...) {
      costs.restore();searchBody(measured);throw;
    }
  }

};
}  // namespace ic382_planners
PLUGINLIB_EXPORT_CLASS(ic382_planners::ClearanceLattice, nav2_core::GlobalPlanner)
