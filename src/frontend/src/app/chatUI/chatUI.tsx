"use client"
import { ChatBubble, ChatBubbleAvatar, ChatBubbleMessage, ChatBubbleAction, ChatBubbleActionWrapper } from '@/components/ui/chat/chat-bubble'
import { ChatMessageList } from '@/components/ui/chat/chat-message-list'
import { ChatButton } from './chatButton';
import { useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal } from 'lucide-react';


interface Message {
    id: number;
    sender: "user" | "bot";
    message: string;
    isLoading?: boolean;
}

const messages: Message[] = [
    {
        id: 1,
        message: 'Hello, how has your day been? I can help you with any questions you have with the report',
        sender: 'bot',
        isLoading: false
    },
    {
        id: 2,
        message: 'What strategies can I use to further secure my app given the report has been generated',
        sender: 'user',
        isLoading: false
    },
    {
        id: 3,
        message: '',
        sender: 'bot',
        isLoading: true,
    },
];


export default function ChatComponent() {

    const [newMessages, setMessages] = useState<Message[]>(messages);
    const [isMessageCompleted, setMessageCompleted] = useState<Boolean>(true);


    const submitButtonEvent = (message: any, event: React.FormEvent<HTMLFormElement>) => {
        let messageLength = newMessages.length;
        let obj = newMessages[messageLength - 1];
        if (obj.isLoading) {
            setMessageCompleted(false);
            setTimeout(() => {
                setMessageCompleted(true)
            }, 10000);
            return;
        }

        let newMessage: Message = { id: newMessages.length, message: message, sender: 'user', isLoading: false };
        let botMessage: Message = { id: newMessages.length + 1, message: '', sender: 'bot', isLoading: true }
        setMessages((prevMessages: Message[]) => [
            ...prevMessages,
            newMessage,
            botMessage
        ])
        event.currentTarget[0].value = "";
    }

   

    return (
        <div>
            {
                !isMessageCompleted ?
                    <>
                        <Alert>
                            <Terminal className="h-4 w-4" />
                            <AlertTitle>Heads up!</AlertTitle>
                            <AlertDescription>
                                Please try to send a message when the ongoing message has received a reply from the AI chatbot.
                            </AlertDescription>
                        </Alert>
                    </>
                    :
                    <></>
            }

            <ChatMessageList>
                {newMessages.map((message, index) => {
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
            <ChatButton submitButton={submitButtonEvent}></ChatButton>

        </div>



    )
}
