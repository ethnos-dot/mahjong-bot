"use client";

export default function GamePicker({ onPick }: { onPick: (g: "sg" | "riichi") => void }) {
  return (
    <div>
      <h1>What are you playing?</h1>
      <div className="choices">
        <div className="choice-btn" onClick={() => onPick("sg")}>
          Singaporean
          <small>4-player payout tracker</small>
        </div>
        <div className="choice-btn" onClick={() => onPick("riichi")}>
          Riichi
          <small>hand calculator</small>
        </div>
      </div>
    </div>
  );
}
