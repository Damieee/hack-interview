import { useCallback, useRef, useState } from "react";

type Options = {
  onSegment: (blob: Blob) => Promise<void> | void;
};

export function useRecorder({ onSegment }: Options) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];
        stream.getTracks().forEach((track) => track.stop());

        try {
          await onSegment(blob);
        } catch (segmentError) {
          setError(
            segmentError instanceof Error
              ? segmentError.message
              : "Failed to process audio."
          );
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to access microphone."
      );
    }
  }, [onSegment]);

  const stop = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
      setIsRecording(false);
    }
  }, []);

  return { isRecording, start, stop, error };
}

