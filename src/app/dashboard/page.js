'use client';
import { useState, useEffect, useRef } from 'react';

export default function Dashboard() {
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedPdf, setSelectedPdf] = useState(null);
  const [conversationThreads, setConversationThreads] = useState([]);
  const [chatInput, setChatInput] = useState('');

  const fileListRef = useRef(null);
  const conversationRef = useRef(null);
  const chatSectionRef = useRef(null);

  // Auto-scroll functionality
  const scrollToBottom = (ref) => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  };

  useEffect(() => {
    // Scroll to the bottom of the conversation section whenever a new thread is added
    scrollToBottom(conversationRef);
  }, [conversationThreads]);

  useEffect(() => {
    // Scroll to the bottom of the chat section when the message changes
    scrollToBottom(chatSectionRef);
  }, [chatInput]);

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-900 via-gray-800 to-black text-white">
      <div className="flex-grow flex flex-col md:flex-row">

        {/* First Column: 20% width for Upload PDFs & List of Uploaded PDFs */}
        <div className="w-full md:w-1/5 p-4 border-r border-gray-700 flex flex-col space-y-4">
          {/* Upload PDFs & List of Uploaded PDFs */}
          <div>
            <h2 className="text-lg font-medium text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300 mb-2">
              Upload PDFs
            </h2>
            <input
              type="file"
              multiple
              accept="application/pdf"
              onChange={() => {}}
              className="block text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:bg-cyan-500 file:text-black hover:file:bg-teal-400"
            />
          </div>
          {/* List of Uploaded PDFs */}
          <div ref={fileListRef} className="overflow-y-auto h-36">
            <ul className="text-sm">
              {uploadedFiles.map((file, index) => (
                <li key={index} className="cursor-pointer hover:underline">
                  {file.name}
                </li>
              ))}
            </ul>
          </div>

          <div className="border-b border-gray-700"></div>

          {/* Conversation Threads */}
          <div ref={conversationRef} className="mt-4 h-36 bg-gray-700 rounded-lg p-4 overflow-y-auto">
            <h2 className="text-lg font-medium text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300 mb-2">
              Conversation Threads
            </h2>
            {conversationThreads.length === 0 ? (
              <p className="text-gray-400">No conversations yet.</p>
            ) : (
              conversationThreads.map((thread, index) => (
                <div
                  key={index}
                  className={`p-2 rounded-md mb-2 ${
                    thread.role === 'user' ? 'bg-cyan-500 text-black' : 'bg-gray-600'
                  }`}
                >
                  <p>{thread.message}</p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="border-l border-gray-700"></div>

        {/* Second Column: PDF Viewer (50% width) */}
        <div className="w-full md:w-1/2 p-4 border-x border-gray-700">
          <h2 className="text-lg font-medium text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300 mb-2">
            PDF Viewer
          </h2>
          {selectedPdf ? (
            <iframe
              src={selectedPdf.url}
              title="Selected PDF"
              className="w-full h-96 rounded-lg"
            ></iframe>
          ) : (
            <p className="text-gray-400">Select a PDF to view its content.</p>
          )}
        </div>

        <div className="border-l border-gray-700"></div>

        {/* Third Column: Chat Section (30% width) */}
        <div className="w-full md:w-1/3 p-4 relative">
          <h2 className="text-lg font-medium text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300 mb-2">
            Chat with AI
          </h2>
          <div
            ref={chatSectionRef}
            className="h-60 bg-gray-700 rounded-lg p-4 overflow-y-auto flex flex-col mb-10"
          >
            {conversationThreads.length === 0 ? (
              <p className="text-gray-400">Start a conversation with the AI.</p>
            ) : (
              conversationThreads.map((thread, index) => (
                <div
                  key={index}
                  className={`p-2 rounded-md mb-2 ${
                    thread.role === 'user' ? 'bg-cyan-500 text-black' : 'bg-gray-600'
                  }`}
                >
                  <p>{thread.message}</p>
                </div>
              ))
            )}
          </div>

          {/* Fixed Message Input Box */}
          <div className="absolute bottom-0 left-0 w-full bg-gray-900 p-4 flex items-center border-t border-gray-700">
            <input
              type="text"
              placeholder="Type your message..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="w-full px-4 py-2 text-lg text-gray-300 bg-gray-600 rounded-lg border border-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <button
              className="ml-4 px-8 py-2 text-lg font-medium text-black bg-gradient-to-r from-cyan-500 to-teal-400 rounded-full shadow-lg hover:shadow-2xl focus:outline-none transition duration-300"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
