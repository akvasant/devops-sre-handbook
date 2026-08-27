class Solution:
    def longestUniqueSubstr(self, s):
        # code here
        seen = set ()
        left = 0
        result = []
        max_len = 0

        for right in range(len(s)):
            while s[right] in seen:
                seen.remove(s[left])
                left += 1 

            seen.add(s[right])
            current = s[left:right +1]

            if len(current) > max_len:
                max_len = len(current)
                result = [current]
            elif len(current) == max_len:
                result.append(current)
        print("Length:", max_len)
        print("Strings:", result)

        return max_len

if __name__ == "__main__":
    s = "Hello My Name is Vasanth"
    solution = Solution()
    solution.longestUniqueSubstr(s)
    
