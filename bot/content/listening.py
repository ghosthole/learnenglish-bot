"""Аудирование: короткие истории уровня A2–B1 и подборка видео.

Истории озвучиваются ботом (edge-tts), после прослушивания — вопросы на понимание.
В тексты специально вшита грамматика из уроков: Past Simple, if-предложения,
Present Perfect, артикли и предлоги.
"""
from dataclasses import dataclass

from bot.content.grammar import Question, choice


@dataclass
class Story:
    id: str
    title: str
    level: str
    text: str
    questions: list[Question]


STORIES: list[Story] = [
    Story(
        id="rainy_day",
        title="☔ Rainy Monday",
        level="A2",
        text=(
            "Yesterday was a terrible day. I woke up late because my alarm didn't ring. "
            "I didn't have breakfast and I ran to the bus stop. It was cloudy, but I forgot to take my umbrella. "
            "Of course, it started to rain, and I got wet. At work, my boss looked at me and laughed. "
            "In the evening, I bought a new umbrella. Now I always keep it in my bag."
        ),
        questions=[
            choice("Why did the speaker wake up late?", ["He was ill", "His alarm didn't ring", "He went to bed late"], 1,
                   "My alarm didn't ring."),
            choice("What did he forget?", ["His phone", "His umbrella", "His breakfast"], 1,
                   "I forgot to take my umbrella."),
            choice("What did he do in the evening?", ["Bought an umbrella", "Watched a series", "Called his boss"], 0,
                   "In the evening, I bought a new umbrella."),
        ],
    ),
    Story(
        id="table_for_two",
        title="🍝 A table for two",
        level="A2",
        text=(
            "Waiter: Good evening! Do you have a reservation? "
            "Anna: Yes, I booked a table for two people at eight o'clock. The name is Anna. "
            "Waiter: Ah, yes. Follow me, please. Here is the menu. "
            "Anna: Thank you. Is the tomato soup spicy? "
            "Waiter: A little. But the mushroom soup isn't spicy at all. "
            "Anna: Great, I'll have the mushroom soup and a glass of water, please. "
            "Waiter: Of course. Anything for dessert? "
            "Anna: Maybe later, thanks."
        ),
        questions=[
            choice("What time is the reservation?", ["At 7", "At 8", "At 9"], 1, "At eight o'clock."),
            choice("What does Anna order?", ["Tomato soup", "Mushroom soup", "Dessert"], 1,
                   "I'll have the mushroom soup."),
            choice("Which soup is a little spicy?", ["Tomato", "Mushroom", "Both"], 0,
                   "The tomato soup is a little spicy."),
        ],
    ),
    Story(
        id="binge",
        title="📺 One more episode",
        level="A2",
        text=(
            "Last Friday I started watching a new series. I only wanted to watch one episode, "
            "but every episode ended on a cliffhanger. So I watched another one, and another one. "
            "At three in the morning I finished the whole season! "
            "On Saturday I was exhausted, but I don't regret it. The plot was amazing, "
            "and the main character is now my favourite. The bad news? The next season comes out next year."
        ),
        questions=[
            choice("How many episodes did the speaker want to watch?", ["One", "Three", "The whole season"], 0,
                   "I only wanted to watch one episode."),
            choice("When did he finish the season?", ["At midnight", "At 3 a.m.", "On Saturday evening"], 1,
                   "At three in the morning."),
            choice("When does the next season come out?", ["Next month", "Next week", "Next year"], 2,
                   "The next season comes out next year."),
        ],
    ),
    Story(
        id="airport",
        title="✈️ At the airport",
        level="B1",
        text=(
            "Attention, please. Flight VN 312 to Hanoi has a delay of two hours because of bad weather. "
            "The new departure time is 11:40. Passengers should go to gate 15. "
            "Please have your passport and boarding pass ready. "
            "We are sorry for the inconvenience. Free drinks are available at the café near gate 12."
        ),
        questions=[
            choice("Where is the flight going?", ["Tokyo", "Hanoi", "Bangkok"], 1, "Flight to Hanoi."),
            choice("Why is there a delay?", ["Bad weather", "A technical problem", "Late passengers"], 0,
                   "Because of bad weather."),
            choice("Which gate should passengers go to?", ["12", "15", "40"], 1, "Go to gate 15."),
        ],
    ),
    Story(
        id="used_to",
        title="🧠 I used to think…",
        level="B1",
        text=(
            "I used to think that learning languages was impossible for me. At school I hated English lessons. "
            "But two years ago I started watching series with English subtitles. At first I understood almost nothing. "
            "Then I began to write down new words, and I repeated them every day. "
            "Now I understand much more than I expected. I still make mistakes, but I'm not afraid of them anymore."
        ),
        questions=[
            choice("How did the speaker feel about English at school?", ["Loved it", "Hated it", "Didn't study it"], 1,
                   "At school I hated English lessons."),
            choice("What helped him?", ["A teacher", "Series with subtitles", "Living abroad"], 1,
                   "I started watching series with English subtitles."),
            choice("What does 'used to think' mean here?", ["He still thinks so", "He thought so before, not now",
                                                            "He will think so"], 1,
                   "used to = раньше, а теперь нет."),
        ],
    ),
    Story(
        id="if_i_had",
        title="💸 If I had a million",
        level="B1",
        text=(
            "If I had a million dollars, I wouldn't buy an expensive car. I would travel around Asia first. "
            "I would start in Vietnam, because the food there is delicious and cheap. "
            "Then I would fly to Japan and stay in a traditional hotel. "
            "If I had more time after that, I would learn Japanese. "
            "But I don't have a million dollars, so this summer I'm going to visit my grandmother in the countryside."
        ),
        questions=[
            choice("Where would the speaker start the trip?", ["Japan", "Vietnam", "Thailand"], 1,
                   "I would start in Vietnam."),
            choice("Would he buy an expensive car?", ["Yes", "No", "Maybe"], 1, "I wouldn't buy an expensive car."),
            choice("What is he really going to do this summer?", ["Go to Japan", "Visit his grandmother",
                                                                 "Learn Japanese"], 1,
                   "I'm going to visit my grandmother."),
        ],
    ),
    Story(
        id="hostel",
        title="🏨 Check-in at a hostel",
        level="A2",
        text=(
            "Receptionist: Hi, welcome to Sakura Hostel! Can I see your passport? "
            "Guest: Sure, here you are. I have a reservation for three nights. "
            "Receptionist: Perfect. You're in room 204, on the second floor. Breakfast is from seven to ten. "
            "Check-out is at eleven. "
            "Guest: Is there Wi-Fi in the room? "
            "Receptionist: Yes, the password is on your key card. Enjoy your stay!"
        ),
        questions=[
            choice("How many nights is the guest staying?", ["Two", "Three", "Four"], 1, "Three nights."),
            choice("What time is check-out?", ["10", "11", "12"], 1, "Check-out is at eleven."),
            choice("Where is the Wi-Fi password?", ["On the wall", "On the key card", "At reception"], 1,
                   "The password is on your key card."),
        ],
    ),
    Story(
        id="never_been",
        title="🗺 Have you ever…?",
        level="B1",
        text=(
            "Tom: Have you ever been abroad? "
            "Kate: Yes, I've been to Turkey and Georgia. What about you? "
            "Tom: I've never been abroad. I've only travelled around Russia. "
            "Kate: Really? Where would you like to go? "
            "Tom: Japan, definitely. I've already saved some money, but I haven't bought the tickets yet. "
            "Kate: You should go in spring. The cherry blossoms are beautiful!"
        ),
        questions=[
            choice("Which countries has Kate visited?", ["Japan and Turkey", "Turkey and Georgia", "Georgia and Japan"], 1,
                   "I've been to Turkey and Georgia."),
            choice("Has Tom bought the tickets?", ["Yes", "Not yet", "He doesn't want to"], 1,
                   "I haven't bought the tickets yet."),
            choice("When does Kate recommend going?", ["In spring", "In summer", "In winter"], 0,
                   "You should go in spring."),
        ],
    ),
    Story(
        id="weekend_plans",
        title="🎉 Weekend plans",
        level="A2",
        text=(
            "Hey! What are you doing this weekend? On Saturday I'm meeting some friends in the city centre. "
            "We're going to try a new Vietnamese restaurant. Then, if the weather is good, we'll walk in the park. "
            "If it rains, we'll go to the cinema instead. On Sunday I'm going to stay at home, "
            "tidy up my room and do the laundry. Boring, I know! Do you want to join us on Saturday?"
        ),
        questions=[
            choice("What kind of restaurant are they going to try?", ["Japanese", "Vietnamese", "Italian"], 1,
                   "A new Vietnamese restaurant."),
            choice("What will they do if it rains?", ["Stay home", "Go to the cinema", "Walk in the park"], 1,
                   "If it rains, we'll go to the cinema."),
            choice("What is the speaker doing on Sunday?", ["Meeting friends", "Housework", "Travelling"], 1,
                   "Tidy up my room and do the laundry."),
        ],
    ),
    Story(
        id="lost_passport",
        title="😱 The lost passport",
        level="B1",
        text=(
            "Last summer my friend and I went to Istanbul. On the second day I couldn't find my passport. "
            "I was so worried! We looked everywhere in the hotel room. Then we went back to the café where we had "
            "had breakfast. The waiter smiled and gave me my passport. He had found it under the table. "
            "I was so relieved that I left a big tip. If he hadn't found it, I would have missed my flight home."
        ),
        questions=[
            choice("Where did they go last summer?", ["Istanbul", "Tbilisi", "Antalya"], 0, "We went to Istanbul."),
            choice("Who found the passport?", ["A police officer", "His friend", "A waiter"], 2,
                   "The waiter … had found it under the table."),
            choice("How did the speaker feel at the end?", ["Annoyed", "Relieved", "Disappointed"], 1,
                   "I was so relieved."),
        ],
    ),
]

STORIES_BY_ID = {s.id: s for s in STORIES}


@dataclass
class VideoTip:
    title: str
    url: str
    why: str


# Ссылки на поиск YouTube вместо конкретных роликов — так они не «протухают».
VIDEO_TIPS: list[VideoTip] = [
    VideoTip("BBC Learning English — 6 Minute English",
             "https://www.youtube.com/results?search_query=6+minute+english+bbc+learning+english",
             "6 минут, два ведущих, медленная чёткая речь. Идеально для A2→B1."),
    VideoTip("Easy English — уличные интервью",
             "https://www.youtube.com/results?search_query=easy+english+street+interviews",
             "Живая речь обычных людей + двойные субтитры."),
    VideoTip("Learn English with TV Series",
             "https://www.youtube.com/results?search_query=learn+english+with+tv+series",
             "Разбор сцен из сериалов: Friends, The Office, Breaking Bad."),
    VideoTip("English with Lucy",
             "https://www.youtube.com/results?search_query=english+with+lucy",
             "Британский акцент, грамматика и произношение простыми словами."),
    VideoTip("Comprehensible Input — English A2",
             "https://www.youtube.com/results?search_query=english+comprehensible+input+A2+listening",
             "Истории на понятном уровне: слушаешь и всё понимаешь из контекста."),
    VideoTip("Friends с английскими субтитрами",
             "https://www.youtube.com/results?search_query=friends+scenes+english+subtitles",
             "Ситком = короткие бытовые фразы. Начни с отдельных сцен."),
]
