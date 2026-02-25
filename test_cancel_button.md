# Testing the Cancel Button

## Setup
1. Open http://localhost:5173 in your browser
2. Click on "Ash" in the sidebar

## Test 1: Cancel Button Visibility
1. Type a message: "Count from 1 to 100 slowly"
2. Press Enter or click Send
3. **Expected**:
   - The blue send button should immediately change to a red cancel button
   - The cancel button should have a square/stop icon
   - The button should have the title "Cancel (ESC)"

## Test 2: Cancel via Button Click
1. While Ash is responding (or queued), click the red cancel button
2. **Expected**:
   - The response should stop
   - You should see "[Response cancelled]" in the chat
   - The cancel button should change back to the send button
   - The input field should be enabled again

## Test 3: Cancel via ESC Key
1. Send another message to Ash
2. While she's responding, press the ESC key on your keyboard
3. **Expected**:
   - Same behavior as clicking the cancel button

## Test 4: Canceling While Queued
1. If Ash is busy, send a message (it will be queued)
2. You should see "Ash is responding to another team member. Your message is queued..."
3. The cancel button should still be visible
4. Click cancel or press ESC
5. **Expected**:
   - The queued message should be cancelled
   - You can send a new message

## Current Status
- ✅ Backend cancel endpoint implemented
- ✅ Frontend cancel function added to client.js
- ✅ Cancel button UI added to ChatPanel.svelte
- ✅ ESC key handler implemented
- ✅ Fixed: Cancel button now shows while message is queued
- The cancel button should now be visible when you send a message to Ash