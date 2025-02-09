"use client"
import React from "react";
import ChatComponent from "./chatUI"; // Your AI Chat UI component
import { candyWrapperTheme, JsonEditor } from 'json-edit-react';
import { resData } from "../display/data";

const SplitScreen = () => {

    const data = JSON.parse(sessionStorage.getItem('data'));

    return (
        <div className="flex h-screen">
            {/* Left Side - File Viewer */}
            {/* <div className="w-1/2 border-r p-4"> */}
            {/* <div className="w-[400px] max-w-[400px] h-full overflow-y-auto border-r p-4"></div> */}
            <div className="w-1/2 h-full overflow-y-auto border-r p-4">
            <div className="w-[800px] h-[1200px] bg-gray-100 p-4">
            <JsonEditor
                    data={data}
                    theme={candyWrapperTheme}
                    restrictEdit={true}
                    restrictDelete={true}
                    restrictAdd={true}
                    enableClipboard={true}
                    minWidth={800}
                />
            </div>
            </div>
            {/* Right Side - Chat UI */}
            <div className="w-1/2 h-[600] overflow-y-auto border-r p-4">
                <ChatComponent />
            </div>
        </div>
    );
};

export default SplitScreen;