        except Exception as exc:
            result["warnings"].append(source + ": " + type(exc).__name__ + ": " + str(exc)[:160])
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SR:", [(e["source"], e["segments_count"]) for e in result["episodes"]], result["warnings"])

if __name__ == "__main__":
    main()def process_episode(model, episode, previous, result):
    old = next((e for e in previous.get("episodes", []) if e.get("audio") == episode["audio"] and e.get("transcribed")), None)
    if old:
        result["episodes"].append(old)
        return
    segments, language = transcribe(model, episode)
    matches = [s for s in segments if KEYWORDS.search(s["text"])]
    episode["language"] = language
    episode["transcribed"] = bool(segments)
    episode["segments_count"] = len(segments)
    # Ta med omgivande meningar för sammanhang, men aldrig påstå att detta är manuellt faktagranskat.
    episode["excerpts"] = matches[:12]
    result["episodes"].append(episode)


