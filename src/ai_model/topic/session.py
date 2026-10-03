class Session:

    def __init__(self):
        # Broad subject.
        # This is the chat boundary.
        self.subject = None

        # Current knowledge hierarchy.
        self.chapter = None
        self.topic = None
        self.subtopic = None

        # Conversation history.
        self.history = []

    def reset(self):
        self.subject = None
        self.chapter = None
        self.topic = None
        self.subtopic = None
        self.history = []


session = Session()