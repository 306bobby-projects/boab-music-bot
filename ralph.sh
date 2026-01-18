#!/bin/bash

# Configuration
EXIT_PHRASE="TASK PROMISE END"
TEMP_LOG="/tmp/ralph_turn_$(date +%s).log"

# SETTING: Auto-Edit
APPROVAL_MODE="--approval-mode yolo"

echo "Starting Ralph Loop..."
echo "Mode: YOLO"
echo "Temp Log: $TEMP_LOG"
echo "Press [CTRL+C] to interrupt manually."

# Cleanup temp file on exit
trap "rm -f $TEMP_LOG; exit" INT TERM EXIT

while true; do
    echo "----------------------------------------------------------------"
    echo "Starting new agent cycle..."

    PROMPT="
You are an autonomous developer agent working on this repository.

### YOUR INSTRUCTIONS
1. READ 'INFORMATION.md' for context.
2. READ 'TODO.md' for tasks.
3. SELECT the highest-priority task.
4. EXECUTE the necessary code changes or shell commands to complete it.
5. UPDATE 'TODO.md': Mark the task as done.
6. UPDATE 'INFORMATION.md': Record any new learnings.
7. GENERATE SUMMARY: Output a single line starting with 'COMMIT_MSG:' followed by a concise summary of your changes.
8. Quit when finished with your single task

### TERMINATION
Check 'TODO.md'. If ALL tasks in that list are marked as completed (e.g. [x] or moved to Done), and ONLY then, output exactly:
$EXIT_PHRASE
"

    # Execute Agent
    # CHANGE 1: Added '2>&1' to capture error messages (stderr) into the log
    gemini $APPROVAL_MODE "$PROMPT" 2>&1 | tee "$TEMP_LOG"

    # CHANGE 2: Rate Limit Detection
    # If we see 429 or Quota errors, kill the script immediately.
    if grep -qE "429|Quota exceeded|Resource exhausted|Too Many Requests" "$TEMP_LOG"; then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "CRITICAL: API Rate Limit Detected. Stopping loop to protect account."
        echo "See log for details: $TEMP_LOG"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        exit 1
    fi

    # Check for Normal Exit Condition
    if grep -q "$EXIT_PHRASE" "$TEMP_LOG"; then
        echo "----------------------------------------------------------------"
        echo "Agent signaled completion with '$EXIT_PHRASE'."
        break
    fi

    # Extract Commit Message
    RAW_MSG=$(grep "COMMIT_MSG:" "$TEMP_LOG" | head -n 1)
    CLEAN_MSG=$(echo "$RAW_MSG" | sed 's/COMMIT_MSG: //')
    
    if [ -z "$CLEAN_MSG" ]; then
        CLEAN_MSG="Ralph Loop: Auto-update"
    fi

    echo "Committing with message: '$CLEAN_MSG'"

    # Git Checkpoint
    git add .
    git commit -m "$CLEAN_MSG" --no-verify

    echo "----------------------------------------------------------------"
    echo "Cycle complete. Restarting in 3 seconds..."
    sleep 3
done
