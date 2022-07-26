#import <Cocoa/Cocoa.h>

void*
makePath (void)
{
  NSBezierPath *path = [[NSBezierPath alloc] init];
  return path;
}

void
move_to (void *funcs,
         void *draw_data,
         void *st,
         float to_x,
         float to_y,
         void *user_data)
{
  NSBezierPath *path = (NSBezierPath *) user_data;
  [path moveToPoint: NSMakePoint(to_x, to_y)];
}

void
line_to (void *funcs,
         void *draw_data,
         void *st,
         float to_x,
         float to_y,
         void *user_data)
{
  NSBezierPath *path = (NSBezierPath *) user_data;
  [path lineToPoint: NSMakePoint(to_x, to_y)];
}

void
cubic_to (void *funcs,
          void *draw_data,
          void *st,
          float control1_x,
          float control1_y,
          float control2_x,
          float control2_y,
          float to_x,
          float to_y,
          void *user_data)
{
  NSBezierPath *path = (NSBezierPath *) user_data;
  [path curveToPoint: NSMakePoint(to_x, to_y)
       controlPoint1: NSMakePoint(control1_x, control1_y)
       controlPoint2: NSMakePoint(control2_x, control2_y)
  ];
}

void close_path (void *funcs,
                 void *draw_data,
                 void *st,
                 void *user_data)
{
  NSBezierPath *path = (NSBezierPath *) user_data;
  [path closePath];
}
