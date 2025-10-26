import re
import logging

logger = logging.getLogger(__name__)


class ContentFilter:
    def __init__(self, enable=True):
        self.enable = enable
        
        # Default bad words list (Vietnamese)
        self.bad_words = [
            'ngu', 'đần', 'khùng', 'điên', 'dốt', 'tệ',
            'xấu xa', 'đồ ngu', 'ngốc', 'khốn', 'chết tiệt',
            'súc vật', 'đồ súc sinh'
        ]
        
        # Educational responses
        self.educational_responses = {
            'high': [
                "Cô nghe thấy em vừa nói một từ không lịch sự rồi. Em có biết từ đó không tốt không? Cô nghĩ em là học sinh ngoan, em nên nói những lời hay đẹp hơn nhé! Em thử nói lại câu hỏi với những từ lịch sự được không?",
                "Em ơi, những từ ngữ như vậy không phù hợp trong lời nói của một học sinh ngoan đâu. Cô tin em có thể nói điều em muốn bằng cách lịch sự và hay hơn. Em thử lại nhé!",
                "Cô nghĩ em không cố ý nói từ không tốt đó đúng không? Hãy nhớ rằng, lời nói thể hiện con người của em đấy. Em hãy thử hỏi cô lại với những từ đẹp hơn nhé!"
            ],
            'medium': [
                "Em ơi, từ đó không hay lắm. Em có thể nói theo cách khác được không?",
                "Cô nghĩ em nên nói lịch sự hơn. Hãy thử lại nhé!",
                "Lời nói không tốt đâu em. Em thử nói lại được không?"
            ],
            'low': [
                "Từ đó không phù hợp. Hãy nói lịch sự hơn.",
                "Không nên nói như vậy. Thử lại nhé!",
                "Hãy dùng từ ngữ lịch sự hơn."
            ]
        }
    
    def check_and_filter(self, text):
        """Check if text contains bad words"""
        if not self.enable:
            return {'contains_bad_words': False, 'found_words': []}
        
        text_lower = text.lower()
        found_words = []
        
        for word in self.bad_words:
            if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
                found_words.append(word)
        
        return {
            'contains_bad_words': len(found_words) > 0,
            'found_words': found_words
        }
    
    def get_educational_response(self, found_words, politeness_level='high'):
        """Get an educational response for inappropriate language"""
        import random
        
        responses = self.educational_responses.get(politeness_level, self.educational_responses['high'])
        return random.choice(responses)
    
    def add_bad_word(self, word):
        """Add a word to the filter list"""
        if word not in self.bad_words:
            self.bad_words.append(word.lower())
            logger.info(f"Added '{word}' to bad words list")
