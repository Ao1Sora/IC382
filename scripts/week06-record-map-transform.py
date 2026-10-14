import rclpy,time,json,math
from tf2_ros import Buffer,TransformListener
rclpy.init();n=rclpy.create_node('ic382_record_map_frame');b=Buffer();t=TransformListener(b,n)
end=time.time()+5
while time.time()<end:rclpy.spin_once(n,timeout_sec=.1)
tf=b.lookup_transform('map','odom',rclpy.time.Time());p=tf.transform.translation;q=tf.transform.rotation
data={'translation':[p.x,p.y,p.z],'rotation':[q.x,q.y,q.z,q.w]};open('/workspace/dev/map/map_to_odom.json','w').write(json.dumps(data,indent=2));print('MAP_FRAME_RECORDED',flush=True)
n.destroy_node();rclpy.shutdown()
