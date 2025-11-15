import { useCallback, useRef, useState } from "react";

type Options = {
  onSegment: (blob: Blob) => Promise<void> | void;
};

export function useRecorder({ onSegment }: Options) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const activeStreamsRef = useRef<MediaStream[]>([]);

  const start = useCallback(async () => {
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      let systemStream: MediaStream | null = null;
      if (navigator.mediaDevices?.getDisplayMedia) {
        try {
          systemStream = await navigator.mediaDevices.getDisplayMedia({
            audio: true,
            video: false,
          });
        } catch (displayErr) {
          console.warn("System audio capture unavailable:", displayErr);
        }
      }

      const tracks = [
        ...micStream.getAudioTracks(),
        ...(systemStream?.getAudioTracks() ?? []),
      ];

      if (!tracks.length) {
        throw new Error("No audio sources available.");
      }

      const combinedStream = new MediaStream(tracks);
      activeStreamsRef.current = [micStream, systemStream].filter(
        (stream): stream is MediaStream => Boolean(stream),
      );

      const recorder = new MediaRecorder(combinedStream, {
        mimeType: "audio/webm",
      });
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];
        combinedStream.getTracks().forEach((track) => track.stop());
        activeStreamsRef.current.forEach((stream) => {
          stream.getTracks().forEach((track) => track.stop());
        });
        activeStreamsRef.current = [];

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
