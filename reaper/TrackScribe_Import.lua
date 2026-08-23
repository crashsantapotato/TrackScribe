-- Common TrackScribe importer for REAPER 7.x. Called by a project wrapper.
local M = {}

-- Built-in action: File: New project tab (verified with REAPER 7.79).
local NEW_PROJECT_TAB = 40859

local function source_length_seconds(project, source)
  local length, is_qn = reaper.GetMediaSourceLength(source)
  if is_qn then
    return reaper.TimeMap2_QNToTime(project, length)
  end
  return length
end

local function add_source_track(project, artifact)
  local index = reaper.CountTracks(project)
  reaper.InsertTrackInProject(project, index, 0)
  local track = reaper.GetTrack(project, index)
  assert(track, "Could not create track: " .. artifact.name)
  reaper.GetSetMediaTrackInfo_String(track, "P_NAME", artifact.name, true)

  -- forcenoMidiImp avoids preference-driven conversion and MIDI import dialogs.
  local no_midi_import = artifact.media_type == "midi"
  local source = reaper.PCM_Source_CreateFromFileEx(artifact.path, no_midi_import)
  assert(source, "Could not open media source: " .. artifact.path)
  local item = reaper.AddMediaItemToTrack(track)
  local take = reaper.AddTakeToMediaItem(item)
  assert(item and take, "Could not create media item: " .. artifact.path)
  assert(reaper.SetMediaItemTake_Source(take, source), "Could not set media source")
  reaper.SetMediaItemPosition(item, 0.0, false)
  reaper.SetMediaItemInfo_Value(item, "C_BEATATTACHMODE", 0)
  reaper.SetMediaItemLength(item, source_length_seconds(project, source), false)
  reaper.SetMediaItemTakeInfo_Value(take, "D_PLAYRATE", 1.0)
  reaper.SetMediaItemTakeInfo_Value(take, "D_PITCH", 0.0)
  return item, take
end

local function clean_field(value)
  return tostring(value):gsub("[\t\r\n]", " ")
end

local function write_report(path, imported)
  if not path or path == "" then return end
  local file = assert(io.open(path, "w"))
  file:write("name\tposition\tlength\tplayrate\tpitch\tis_midi\tnotes\tfirst_start\tfirst_end\n")
  for _, entry in ipairs(imported) do
    local item, take = entry.item, entry.take
    local is_midi = reaper.TakeIsMIDI(take)
    local notes, first_start, first_end = 0, "", ""
    if is_midi then
      _, notes = reaper.MIDI_CountEvts(take)
      if notes > 0 then
        local ok, _, _, start_ppq, end_ppq = reaper.MIDI_GetNote(take, 0)
        if ok then
          first_start = reaper.MIDI_GetProjTimeFromPPQPos(take, start_ppq)
          first_end = reaper.MIDI_GetProjTimeFromPPQPos(take, end_ppq)
        end
      end
    end
    file:write(table.concat({
      clean_field(entry.name),
      reaper.GetMediaItemInfo_Value(item, "D_POSITION"),
      reaper.GetMediaItemInfo_Value(item, "D_LENGTH"),
      reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE"),
      reaper.GetMediaItemTakeInfo_Value(take, "D_PITCH"),
      is_midi and "1" or "0", notes, first_start, first_end
    }, "\t"), "\n")
  end
  file:close()
end

function M.import(config)
  assert(config and config.artifacts, "TrackScribe wrapper has no artifacts")
  reaper.Main_OnCommand(NEW_PROJECT_TAB, 0)
  local project = 0
  local imported = {}
  reaper.Undo_BeginBlock2(project)
  reaper.PreventUIRefresh(1)
  local ok, message = xpcall(function()
    -- MIDI transport copies encode absolute seconds at 120 BPM.
    reaper.SetTempoTimeSigMarker(project, -1, 0.0, -1, -1, 120.0, 0, 0, false)
    for _, artifact in ipairs(config.artifacts) do
      local item, take = add_source_track(project, artifact)
      table.insert(imported, {name = artifact.name, item = item, take = take})
    end
    write_report(config.report_path, imported)
  end, debug.traceback)
  reaper.PreventUIRefresh(-1)
  reaper.UpdateArrange()
  reaper.Undo_EndBlock2(project, "Import TrackScribe project", -1)
  if not ok then
    reaper.ReaScriptError("!TrackScribe import failed:\n" .. tostring(message))
  end
end

return M
