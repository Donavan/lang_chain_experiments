import time
import threading
import queue

class TokenBucket:
    def __init__(self, rate, interval):
        self.rate = rate
        self.interval = interval
        self.tokens = queue.Queue(rate)
        self.refill_thread = threading.Thread(target=self.refill)
        self.refill_thread.daemon = True
        self.refill_thread.start()

    def refill(self):
        while True:
            time.sleep(self.interval)
            while not self.tokens.full():
                self.tokens.put(1)

    def consume(self):
        try:
            self.tokens.get_nowait()
            return True
        except queue.Empty:
            return False

    def get_wait_time(self):
        return self.interval
