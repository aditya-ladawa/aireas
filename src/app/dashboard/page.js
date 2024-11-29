'use client';

import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const BASE_URL = process.env.NEXT_PUBLIC_VERCEL_URL || 'http://localhost:3000';

export default function Dashboard() {
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [fileCount, setFileCount] = useState(0);
  const [selectedPdf, setSelectedPdf] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [conversationThreads, setConversationThreads] = useState([]);
  const [isUploading, setIsUploading] = useState(false); // Add loading state for upload

  const conversationRef = useRef(null);
  const chatSectionRef = useRef(null);

  const scrollToBottom = (ref) => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  };

  useEffect(() => {
    fetchUploadedFiles();
  }, []);

  useEffect(() => {
    scrollToBottom(conversationRef);
  }, [conversationThreads]);

  useEffect(() => {
    scrollToBottom(chatSectionRef);
  }, [chatInput]);

  const fetchUploadedFiles = async () => {
    try {
      const response = await axios.get(`${BASE_URL}/api/get_uploaded_files`);
      if (response.status === 200) {
        const formattedFiles = response.data.files?.map((fileName) => ({ name: fileName })) || [];
        setUploadedFiles(formattedFiles);
      }
    } catch (error) {
      console.log('Failed to fetch uploaded files:', error);
    }
  };

  const handleFileSelection = (event) => {
    const selected = Array.from(event.target.files);
    setSelectedFiles(selected);
    setFileCount(selected.length);
  };

  const handleFileUpload = async () => {
    if (selectedFiles.length === 0) return;

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append('files', file);
    });

    setIsUploading(true); // Show loading indicator

    try {
      const response = await axios.post(`${BASE_URL}/api/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.status === 200) {
        fetchUploadedFiles();
        setSelectedFiles([]);
        setFileCount(0);
      }
    } catch (error) {
      console.log('File upload failed:', error);
    } finally {
      setIsUploading(false); // Hide loading indicator
    }
  };

  const handleChatInput = async () => {
    if (!chatInput.trim()) return;

    const newThread = { role: 'user', message: chatInput };
    setConversationThreads((prev) => [...prev, newThread]);

    try {
      const response = await axios.post('/api/chat', { message: chatInput });
      if (response.status === 200) {
        const aiReply = { role: 'ai', message: response.data.reply };
        setConversationThreads((prev) => [...prev, aiReply]);
      }
    } catch (error) {
      console.log('Chat failed:', error);
    } finally {
      setChatInput('');
    }
  };

  const handleFileClick = (file) => {
    setSelectedPdf(file);
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-900 via-gray-800 to-black text-white">
      <div className="flex-grow flex flex-col md:flex-row gap-6 px-6 py-8">
        {/* First Column: Upload PDFs & List of Uploaded PDFs */}
        <div className="w-full md:w-1/5 p-6 border-r border-gray-700 flex flex-col space-y-6 bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg shadow-lg">
          {/* Upload PDF Section */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300">
              Upload PDFs
            </h2>
            <input
              type="file"
              multiple
              accept="application/pdf"
              onChange={handleFileSelection}
              className="block w-full text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:bg-cyan-500 file:text-black hover:file:bg-teal-400 transition duration-300"
            />
            <button
              onClick={handleFileUpload}
              disabled={isUploading} // Disable upload button while uploading
              className={`mt-4 w-full py-2 text-sm font-semibold rounded-lg transition duration-300 ${isUploading ? 'bg-gray-500' : 'bg-gradient-to-r from-cyan-500 to-teal-400 hover:shadow-xl'}`}
            >
              {isUploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>

          {/* Display Pending Files for Upload */}
          <div className="mt-4">
            {fileCount === 0 ? (
              <p className="text-gray-400">No files selected for upload.</p>
            ) : (
              <p className="text-gray-400">{fileCount} file(s) selected.</p>
            )}
          </div>

          {/* Display Uploaded Files */}
          <div className="mt-4">
            <h2 className="text-xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300">
              Uploaded Files
            </h2>
            {uploadedFiles.length === 0 ? (
              <p className="text-gray-400">No uploaded files yet.</p>
            ) : (
              <ul className="text-sm space-y-2">
                {uploadedFiles.map((file, index) => (
                  <li
                    key={index}
                    className="text-white-300 flex justify-between items-center hover:bg-gray-700 p-2 rounded-lg cursor-pointer"
                    onClick={() => handleFileClick(file)}
                  >
                    <span>{file.name}</span>
                    <button className="text-cyan-400 hover:underline">View</button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Display Conversation Threads */}
          <div ref={conversationRef} className="mt-4 h-36 bg-gray-700 rounded-lg p-4 overflow-y-auto">
            <div className="flex justify-between items-center mb-2">
              <h2 className="text-xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300">
                Conversations
              </h2>
              <button
                className="w-6 h-6 flex justify-center items-center bg-cyan-500 text-black font-bold rounded-full hover:bg-cyan-600"
                title="Add new conversation"
              >
                +
              </button>
            </div>
            {conversationThreads.length === 0 ? (
              <p className="text-gray-400">No conversations yet.</p>
            ) : (
              conversationThreads.map((thread, index) => (
                <div
                  key={index}
                  className={`p-3 rounded-lg mb-2 ${thread.role === 'user' ? 'bg-cyan-500 text-black' : 'bg-gray-600'}`}
                >
                  <p className="text-sm">{thread.message}</p>
                </div>
              ))
            )}
          </div>

        </div>

        {/* Second Column: Display PDF Name */}
        <div className="w-full md:w-1/2 p-4 border-x border-gray-700">
          <h2 className="text-lg font-medium text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300 mb-2">
            Selected PDF
          </h2>
          {selectedPdf ? (
            <p className="text-gray-400">{selectedPdf.name}</p>
          ) : (
            <p className="text-gray-400">Select a PDF to view its name.</p>
          )}
        </div>

        {/* Third Column: Chat Section */}
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
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Ask something..."
            className="w-full p-2 rounded-md bg-gray-800 text-white border border-gray-700 focus:outline-none focus:ring-2 focus:ring-cyan-400 transition duration-300"
          />
          <button
            onClick={handleChatInput}
            className="absolute bottom-4 right-4 px-4 py-2 text-sm font-medium text-black bg-gradient-to-r from-cyan-500 to-teal-400 rounded-full hover:shadow-xl transition duration-300"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
