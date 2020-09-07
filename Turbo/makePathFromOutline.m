// #include <stdio.h>
#import <Cocoa/Cocoa.h>


typedef struct
{
  signed long x;
  signed long y;
} point_t;


#define FT_CURVE_TAG( flag )  ( flag & 3 )

#define FT_CURVE_TAG_ON            1
#define FT_CURVE_TAG_CONIC         0
#define FT_CURVE_TAG_CUBIC         2


static void qCurveToOne(NSBezierPath* path, NSPoint pt0, NSPoint pt1, NSPoint pt2)
{
    // from fontTools/pens/basePen.py
    // def _qCurveToOne(self, pt1, pt2):
    //  """This method implements the basic quadratic curve type. The
    //  default implementation delegates the work to the cubic curve
    //  function. Optionally override with a native implementation.
    //  """
    //  pt0x, pt0y = self.__currentPoint
    //  pt1x, pt1y = pt1
    //  pt2x, pt2y = pt2
    //  mid1x = pt0x + 0.66666666666666667 * (pt1x - pt0x)
    //  mid1y = pt0y + 0.66666666666666667 * (pt1y - pt0y)
    //  mid2x = pt2x + 0.66666666666666667 * (pt1x - pt2x)
    //  mid2y = pt2y + 0.66666666666666667 * (pt1y - pt2y)
    //  self._curveToOne((mid1x, mid1y), (mid2x, mid2y), pt2)

    NSPoint handle1, handle2;

    handle1.x = pt0.x + 0.66666666666666667 * (pt1.x - pt0.x);
    handle1.y = pt0.y + 0.66666666666666667 * (pt1.y - pt0.y);
    handle2.x = pt2.x + 0.66666666666666667 * (pt1.x - pt2.x);
    handle2.y = pt2.y + 0.66666666666666667 * (pt1.y - pt2.y);

    [path curveToPoint: pt2
         controlPoint1: handle1
         controlPoint2: handle2
    ];
}


#define MIDPOINT(pt1, pt2) NSMakePoint(((pt1).x + (pt2).x) * 0.5, ((pt1).y + (pt2).y) * 0.5)

// Modulo with Python semantics: result is never negative.
// This macro has a limited range, though: it is only doing the right
// thing if op1 >= -op2, which is good enough for our purposes.
#define PY_MODULO(op1, op2) ((op1) < 0 ? (((op1) + (op2)) % (op2)) : ((op1) % (op2)))


static void drawSegment(NSBezierPath* path,
                        int n_points,
                        point_t* points,
                        int seg_start,
                        int seg_end,
                        char curve_type,
                        char is_quad_blob,
                        char is_final_segment)
{
    unsigned int n_offcurves;

    n_offcurves = PY_MODULO(seg_end - seg_start - 1, n_points);

    if (n_offcurves == 0) {
        if (!is_final_segment) {
            [path lineToPoint:NSMakePoint(points[seg_end].x, points[seg_end].y)];
        }
    } else {
        if (curve_type == FT_CURVE_TAG_CUBIC) {
            // Cubic segment, assuming n_offcurves == 2 here
            int h1_index = PY_MODULO(seg_end - 2, n_points);
            int h2_index = PY_MODULO(seg_end - 1, n_points);
            [path curveToPoint: NSMakePoint(points[seg_end].x, points[seg_end].y)
                 controlPoint1: NSMakePoint(points[h1_index].x, points[h1_index].y)
                 controlPoint2: NSMakePoint(points[h2_index].x, points[h2_index].y)
            ];
        } else {
            // Quadratic segment
            int i;
            NSPoint prev_oncurve;
            if (is_quad_blob) {
                int prev_index = PY_MODULO(seg_start - 1, n_points);
                prev_oncurve = MIDPOINT(points[prev_index], points[seg_start]);
                [path moveToPoint: prev_oncurve];
                n_offcurves++;
                seg_start--;  // it will not be used as an index while negative
            } else {
                prev_oncurve = NSMakePoint(points[seg_start].x, points[seg_start].y);
            }
            for (i = 0; i < n_offcurves; i++) {
                if (i == n_offcurves - 1 && !is_quad_blob) {
                    int off_index = (seg_start + i + 1) % n_points;
                    qCurveToOne(path, prev_oncurve,
                                      NSMakePoint(points[off_index].x, points[off_index].y),
                                      NSMakePoint(points[seg_end].x, points[seg_end].y));
                } else {
                    int off1_index = (seg_start + i + 1) % n_points;
                    int off2_index = (seg_start + i + 2) % n_points;
                    NSPoint implied = MIDPOINT(points[off1_index], points[off2_index]);
                    qCurveToOne(path, prev_oncurve,
                                      NSMakePoint(points[off1_index].x, points[off1_index].y),
                                      implied);
                    prev_oncurve = implied;
                }
            }
        }
    }
}


static void drawContour(NSBezierPath* path,
                        short n_points,
                        point_t* points,
                        char* tags)
{
    int i, first_oncurve = -1;
    int seg_start, seg_end;
    char curve_type = 0;

    for (i = 0; i < n_points; i++) {
        if (FT_CURVE_TAG(tags[i]) == FT_CURVE_TAG_ON) {
            first_oncurve = i;
            break;
        }
    }
    if (first_oncurve == -1) {
        // There are no on-curve points, this is a quad blob
        drawSegment(path, n_points, points, 0, n_points, curve_type, 1, 0);
    } else {
        [path moveToPoint:NSMakePoint(points[first_oncurve].x, points[first_oncurve].y)];
        seg_start = first_oncurve;
        for (i = 1; i <= n_points; i++) {
            int index = (i + first_oncurve) % n_points;
            if (FT_CURVE_TAG(tags[index]) == FT_CURVE_TAG_ON) {
                seg_end = index;
                drawSegment(path, n_points, points, seg_start, seg_end, curve_type, 0, i == n_points);
                seg_start = seg_end;
            } else {
                curve_type = FT_CURVE_TAG(tags[index]);
            }
        }
    }
    if (n_points > 1) {
        [path closePath];
    }
}

void* makePathFromArrays(short n_contours, short n_points, point_t* points, char* tags, short* contours)
{
    int i, j, c_start = 0;

    NSBezierPath *path = [[NSBezierPath alloc] init];

    for (i = 0; i < n_contours; i++) {
        int c_end;
        c_end = contours[i] + 1;
        drawContour(path, c_end - c_start, &points[c_start], &tags[c_start]);
        c_start = c_end;
    }
    return path;
}
