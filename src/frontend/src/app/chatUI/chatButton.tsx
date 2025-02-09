import { ChatInput } from "@/components/ui/chat/chat-input"
import { Button } from "@/components/ui/button"
import { CornerDownLeft } from "lucide-react"

export function ChatButton() {
    return (

        <div className="border-t border-gray-700 p-4 bg-black fixed bottom-0 w-[550]">
            <form
                className="relative rounded-lg border bg-background focus-within:ring-1 focus-within:ring-ring p-1"
            >
                <ChatInput
                    placeholder="Type your message here..."
                    className="min-h-12 resize-none rounded-lg bg-background border-0 p-3 shadow-none focus-visible:ring-0"
                />
                <div className="flex items-center p-3 pt-0">
                    <Button
                        size="sm"
                        className="ml-auto gap-1.5"
                    >
                        Send Message
                        <CornerDownLeft className="size-3.5" />
                    </Button>
                </div>
            </form>
        </div>
    )
}
