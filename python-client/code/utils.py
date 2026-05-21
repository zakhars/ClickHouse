from functools import wraps
import statistics
import time


class Color:
   GREEN  = '\033[92m'
   RED    = '\033[91m'
   YELLOW = '\033[93m'
   BLUE   = '\033[95m'
   WHITE  = '\033[97m'
   RESET  = '\033[0m'


def print_colored(text, color=Color.RESET):
   print(f'{color}{text}{Color.RESET}', flush=True)


# Decorator to measure function execution time and show stats
def avg_time(n_calls=1, verbose=False, return_stats=False, silent=False):
   def decorator(func):
      @wraps(func)
      def wrapper(*args, **kwargs):
         times = []

         result = None
         for i in range(n_calls):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            times.append(end_time - start_time)

         avg_time = statistics.mean(times)
         min_time = min(times)
         max_time = max(times)
         std_dev = statistics.stdev(times) if len(times) > 1 else 0

         if not silent:
            print_colored(f"Stats for function '{func.__name__}': Calls: {n_calls}, Avg: {avg_time:.6f} s ({avg_time * 1000:.3f} ms)", color=Color.YELLOW)
         if verbose:
            print(f"   Min: {min_time:.6f} s")
            print(f"   Max: {max_time:.6f} s")
            print(f"   Stddev: {std_dev:.6f} s")

         if return_stats:
            return result, {
               'avg': avg_time,
               'min': min_time,
               'max': max_time,
               'std': std_dev,
               'times': times
            }
         return result
      return wrapper
   return decorator



def trace(msg, enabled=True):
   def decorator(func):
      @wraps(func)
      def wrapper(*args, **kwargs):
         if enabled:
            print(f"")
            print_colored(f"{msg}... ", color=Сolor.WHITE)
         result = func(*args, **kwargs)
         if enabled:
            print_colored(f"Success", color=Сolor.WHITE)
         return result
      return wrapper
   return decorator


def print_test_header(header):
   print_colored(f'\n\nTEST: {header}', color=Сolor.GREEN)


def print_script_code(prefix, code):
   print(f'\n{prefix} code:', flush=True)
   for script in code:
      print(script, flush=True)
      print('\n')


def is_datetime_type(type_str):
    return 'DateTime64' in str(type_str)


def print_clickhouse_rowset(result, num_rows=0):
   if num_rows < 0: return

   columns = result.column_names
   rows = result.result_rows
   types = result.column_types

   widths = [len(str(col)) for col in columns]
   for row in rows[:10]:
      for i, val in enumerate(row):
         widths[i] = max(widths[i], len(str(val)))

   header = " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(columns))
   print('')
   print(header)
   print("-" * len(header))

   for row in rows[:num_rows]:
      formatted_values = []
      for val, type, width in zip(row, types, widths):
         if is_datetime_type(type):
            microseconds = val.microsecond
            nanoseconds = val.nanosecond if hasattr(val, 'nanosecond') else 0
            total_nanoseconds = microseconds * 1000 + nanoseconds
            val = val.strftime('%Y-%m-%d %H:%M:%S') + f'.{total_nanoseconds:09d}'
         formatted_values.append(str(val).ljust(width))
      row_to_print = " | ".join(formatted_values)
      print(row_to_print)
