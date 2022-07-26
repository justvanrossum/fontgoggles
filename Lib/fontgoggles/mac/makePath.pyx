#cython: language_level=3
from cpython.pycapsule cimport PyCapsule_New
from objc import objc_object
from uharfbuzz import DrawFuncs


cdef extern:
    void *makePath()
    void move_to(void *funcs,
                 void *draw_data,
                 void *st,
                 float to_x,
                 float to_y,
                 void *user_data)

    void line_to(void *funcs,
                 void *draw_data,
                 void *st,
                 float to_x,
                 float to_y,
                 void *user_data)

    void cubic_to(void *funcs,
                  void *draw_data,
                  void *st,
                  float control1_x,
                  float control1_y,
                  float control2_x,
                  float control2_y,
                  float to_x,
                  float to_y,
                  void *user_data)

    void close_path(void *funcs,
                    void *draw_data,
                    void *st,
                    void *user_data)


def makePathFromGlyph(font, gid):
    cdef void *path = makePath()
    path_cap = PyCapsule_New(<void *>path, NULL, NULL)

    funcs = DrawFuncs()

    cap = PyCapsule_New(<void *>&move_to, NULL, NULL)
    funcs.set_move_to_func(cap, path_cap)

    cap = PyCapsule_New(<void *>&line_to, NULL, NULL)
    funcs.set_line_to_func(cap, path_cap)

    cap = PyCapsule_New(<void *>&cubic_to, NULL, NULL)
    funcs.set_cubic_to_func(cap, path_cap)

    cap = PyCapsule_New(<void *>&close_path, NULL, NULL)
    funcs.set_close_path_func(cap, path_cap)

    funcs.get_glyph_shape(font, gid)

    return objc_object(c_void_p=<size_t>path)
