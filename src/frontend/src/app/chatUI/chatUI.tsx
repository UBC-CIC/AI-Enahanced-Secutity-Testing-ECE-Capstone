"use client"
import { ChatBubble, ChatBubbleAvatar, ChatBubbleMessage, ChatBubbleAction, ChatBubbleActionWrapper } from '@/components/ui/chat/chat-bubble'
import { ChatMessageList } from '@/components/ui/chat/chat-message-list'
import { ChatButton } from './chatButton';

const messages = [
    {
        id: 1,
        message: 'Hello, how has your day been? I hope you are doing well.',
        sender: 'user',
    },
    {
        id: 2,
        message: 'Hi, I am doing well, thank you for asking. How can I help you today?',
        sender: 'bot',
    },
    {
        id: 3,
        message: 'Good Bye!',
        sender: 'bot',
        isLoading: false,
    },
];

export default function ChatComponent() {

    return (
        <div>
            <ChatMessageList>
                {messages.map((message, index) => {
                    const variant = message.sender === 'user' ? 'sent' : 'received';
                    return (
                        <ChatBubble key={message.id} variant={variant}>
                            <ChatBubbleAvatar fallback={variant === 'sent' ? 'US' : 'AI'} />
                            <ChatBubbleMessage isLoading={message.isLoading}>
                                {message.message}
                            </ChatBubbleMessage>
                        </ChatBubble>
                    )
                })}
            </ChatMessageList>
            <ChatButton></ChatButton>

        </div>



    )
}
