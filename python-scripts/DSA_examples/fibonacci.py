import argparse
def fibonacci(limit):
    a, b = 0, 1
    for i in range(limit):
        print(a, end=' ')
        a, b = b, a+b
    print()

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Fibonacci Script')
  parser.add_argument(
    '--limit',
    type=int,
    default=15,
    help='Enter the Fibonacci limit'
  )
  args = parser.parse_args([])
  print(f"Limit : {args.limit}")
  fibonacci(args.limit)
