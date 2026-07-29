/* ediFabric Native — C ABI for edifabric-x12-tools (Native AOT shared library).
 *
 * All strings/payloads are UTF-8 (byte* + length) unless noted.
 * Every int-returning function: 0 = success, non-zero = error code.
 * Grow-and-retry: InsufficientCapacity (1) means reallocate to *outLen and call again.
 *
 * get_error returns a heap-allocated ANSI C string; free it with free_error.
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
#  ifdef EDIFABRIC_X12_EXPORTS
#    define EDIFABRIC_API __declspec(dllexport)
#  else
#    define EDIFABRIC_API __declspec(dllimport)
#  endif
#else
#  define EDIFABRIC_API __attribute__((visibility("default")))
#endif

#include <stdint.h>

/* Lifecycle / logging */
EDIFABRIC_API int  init_logger(const unsigned char* path_utf8, int path_len, int min_level);
EDIFABRIC_API int  shutdown_logger(void);
EDIFABRIC_API int  clear_cache(void);

/* Licensing */
EDIFABRIC_API int  install_license(const unsigned char* serial, int serial_len);
EDIFABRIC_API int  get_app_version(int* app_version);
EDIFABRIC_API int  get_token(const unsigned char* serial, int serial_len,
                             unsigned char* output, int output_capacity, int* output_length);
EDIFABRIC_API int  validate_token(const unsigned char* token, int token_len);
EDIFABRIC_API int  set_token(const unsigned char* token, int token_len);
EDIFABRIC_API int  get_token_expiration(int64_t* expiration_utc);
EDIFABRIC_API int  set_serial(const unsigned char* serial, int serial_len);

/* Model map (JSON UTF-8) */
EDIFABRIC_API int  set_map(const unsigned char* map, int map_length);

/* Parse / split / build / merge
 * mode: 1=JSON, 2=JSON+Validate, 3=JSON+Validate+Ack
 */
EDIFABRIC_API int  parse(const unsigned char* input, int input_length,
                         int mode,
                         const unsigned char* config, int config_length,
                         unsigned char* output, int output_capacity,
                         int* output_length, int* output_offset);

EDIFABRIC_API int  start_split(const unsigned char* input, int input_length,
                               int mode,
                               const unsigned char* config, int config_length);
EDIFABRIC_API int  split(int* result_size, int* result_offset, unsigned char* last);

EDIFABRIC_API int  build(const unsigned char* input, int input_length,
                         const char* postfix,
                         unsigned char* output, int output_capacity, int* output_length);

EDIFABRIC_API int  start_merge(const unsigned char* input, int input_length);
EDIFABRIC_API int  merge(int* result_size);

EDIFABRIC_API int  get_result(unsigned char* buffer, int buffer_size);

/* Error messages — free with free_error */
EDIFABRIC_API char* get_error(int error_code);
EDIFABRIC_API void  free_error(char* ptr);

#ifdef __cplusplus
}
#endif
